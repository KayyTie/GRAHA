import React, { useState } from 'react';
import { Navbar } from './components/Navbar';
import { Home } from './views/Home';
import { Dashboard } from './views/Dashboard';
import { Learn } from './views/Learn';
import { About } from './views/About';
import { AnimatePresence, motion } from 'framer-motion';
import { StarfieldBackground } from './components/ThreeScene';

const viewOrder = ['home', 'dashboard', 'pipeline', 'about'];

const carouselVariants = {
  enter: {
    x: 0,
    y: 0,
    opacity: 0,
  },
  center: {
    x: 0,
    y: 0,
    opacity: 1,
  },
  exit: {
    x: 0,
    y: 0,
    opacity: 0,
  },
};

const App: React.FC = () => {
  const [currentView, setCurrentView] = useState<string>('home');
  const [direction, setDirection] = useState<number>(1);
  const [isInitialLoad, setIsInitialLoad] = useState<boolean>(true);
  const [backendOnline, setBackendOnline] = useState<boolean>(false);
  const [activeTicId, setActiveTicId] = useState<string | null>(null);
  const [homeTransitioning, setHomeTransitioning] = useState<boolean>(false);
  const [isResultsView, setIsResultsView] = useState<boolean>(false);
  const [isLeavingDashboard, setIsLeavingDashboard] = useState<boolean>(false);

  const handleSetView = (newView: string) => {
    if (newView === currentView) return;

    if (currentView === 'dashboard' && newView !== 'dashboard') {
      setIsLeavingDashboard(true);
      setTimeout(() => {
        setIsLeavingDashboard(false);
      }, 450);
    }

    if (currentView === 'home' && (newView === 'dashboard' || newView === 'pipeline') && !homeTransitioning) {
      setHomeTransitioning(true);
      setTimeout(() => {
        setHomeTransitioning(false);
        if (isInitialLoad) {
          setIsInitialLoad(false);
        }
        const currentIndex = viewOrder.indexOf('home');
        const newIndex = viewOrder.indexOf(newView);
        setDirection(newIndex >= currentIndex ? 1 : -1);
        setCurrentView(newView);
      }, 2500);
      return;
    }
    if (isInitialLoad) {
      setIsInitialLoad(false);
    }
    const currentIndex = viewOrder.indexOf(currentView);
    const newIndex = viewOrder.indexOf(newView);
    const dir = newIndex >= currentIndex ? 1 : -1;
    setDirection(dir);
    setCurrentView(newView);
  };

  const renderView = () => {
    switch (currentView) {
      case 'home':
        return (
          <Home
            setView={handleSetView}
            isTransitioning={homeTransitioning}
            onInitiateScan={() => handleSetView('dashboard')}
          />
        );
      case 'dashboard':
        return (
          <Dashboard
            setBackendOnline={setBackendOnline}
            setActiveTicId={setActiveTicId}
            setIsResultsView={setIsResultsView}
          />
        );
      case 'pipeline':
        return <Learn />;
      case 'about':
        return <About />;
      default:
        return <Home setView={handleSetView} />;
    }
  };

  return (
    <>
      {currentView !== 'dashboard' && !isLeavingDashboard && (
        <div className="fixed inset-0 z-[-1] pointer-events-none">
          <StarfieldBackground />
        </div>
      )}
      {(currentView === 'dashboard' || isLeavingDashboard) && (
        <div className="fixed inset-0 z-[-1] bg-white pointer-events-none transition-opacity duration-300" />
      )}
      <div className={`min-h-screen flex flex-col font-body-md overflow-x-hidden pt-0 transition-colors duration-500 ${
        (currentView === 'dashboard' || isLeavingDashboard) ? 'bg-white text-black selection:bg-black/20 selection:text-black' : 'bg-transparent text-white selection:bg-white/20 selection:text-white'
      }`}>
        <Navbar
          currentView={currentView}
          setView={handleSetView}
          backendOnline={backendOnline}
          activeTicId={activeTicId}
          isResultsView={isResultsView && currentView === 'dashboard'}
        />
        <main className="flex-grow flex flex-col w-full relative overflow-hidden">
          <AnimatePresence custom={{ direction, isInitialLoad }} mode="wait">
            <motion.div
              key={currentView}
              custom={{ direction, isInitialLoad }}
              variants={carouselVariants}
              initial="enter"
              animate="center"
              exit="exit"
              transition={{
                x: { type: 'spring', stiffness: 280, damping: 28 },
                y: { type: 'spring', stiffness: 280, damping: 28 },
                opacity: { duration: 0.35 },
              }}
              className="w-full flex-grow flex flex-col"
            >
              {renderView()}
            </motion.div>
          </AnimatePresence>
        </main>
      </div>
    </>
  );
};

export default App;

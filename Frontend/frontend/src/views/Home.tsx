import React from 'react';
import { PlanetSystem } from '../components/ThreeScene';

interface HomeProps {
  setView: (view: string) => void;
  isTransitioning?: boolean;
  onInitiateScan?: () => void;
}

const styles = {
  heroSection: "relative w-full h-screen flex items-center justify-center overflow-hidden border-b border-outline-variant/30 bg-transparent",
  astraContainer: "absolute top-[15%] left-0 right-0 mx-auto flex flex-col items-center w-full max-w-4xl px-4 pointer-events-none",
  astraText: "font-orbitron text-6xl md:text-[140px] font-normal tracking-[0.1em] text-white/90 animate-expand-tracking leading-none text-center select-none pointer-events-none mix-blend-difference",
  astraDescription: "mt-6 font-orbitron text-sm md:text-base tracking-[0.05em] text-white/75 text-center leading-relaxed select-none pointer-events-none mix-blend-difference",
  coordinates: "absolute bottom-6 right-6 font-label-sm text-label-sm text-outline tracking-widest uppercase pointer-events-none z-10",
  buttonContainer: "absolute bottom-24 left-1/2 transform -translate-x-1/2 flex flex-col sm:flex-row gap-4 justify-center items-center pointer-events-auto z-10",
  primaryBtn: "bg-white text-black font-label-sm text-label-sm uppercase tracking-widest px-8 py-3 hover:bg-gray-200 transition-colors cursor-pointer font-bold"
};

export const Home: React.FC<HomeProps> = ({ setView, isTransitioning = false, onInitiateScan }) => {
  const [whiteFlash, setWhiteFlash] = React.useState(false);

  React.useEffect(() => {
    if (isTransitioning) {
      // Start white flash late (at 1500ms) and fade over 1000ms so it ends at 2500ms
      const timer = setTimeout(() => {
        setWhiteFlash(true);
      }, 1500);
      return () => clearTimeout(timer);
    } else {
      setWhiteFlash(false);
    }
  }, [isTransitioning]);

  const handleScanClick = () => {
    if (onInitiateScan) {
      onInitiateScan();
    } else {
      setView('dashboard');
    }
  };

  return (
    <section 
      className={styles.heroSection} 
      id="three-container"
    >
      <PlanetSystem isTransitioning={isTransitioning} />
      
      <div className={`${styles.astraContainer} transition-opacity duration-[2500ms] ease-in-out ${isTransitioning ? 'opacity-0' : 'opacity-100'}`}>
        <div className={styles.astraText} style={{ paddingLeft: '0.1em' }}>GRAHA</div>
        <p className={styles.astraDescription}>
          AI-Enabled Exoplanet Detection from TESS Light Curves.
        </p>
      </div>
      
      <div className={`${styles.buttonContainer} transition-opacity duration-[2500ms] ease-in-out ${isTransitioning ? 'opacity-0' : 'opacity-100'}`}>
        <button onClick={handleScanClick} className={styles.primaryBtn}>
          Initiate Scan
        </button>
      </div>
      
      <div className={`${styles.coordinates} transition-opacity duration-[2500ms] ease-in-out ${isTransitioning ? 'opacity-0' : 'opacity-100'}`}>
        A PROJECT BY TEAM VOYAGER 3
      </div>

      {/* Pure White Background Flash Overlay - starts late at 1.5s, shorter 1.0s duration, ends at 2.5s */}
      <div 
        className={`fixed inset-0 bg-white transition-opacity duration-[1000ms] ease-in pointer-events-none z-50 ${
          whiteFlash ? 'opacity-100' : 'opacity-0'
        }`} 
      />
    </section>
  );
};

import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { CheckCircle2, Loader2, Hourglass, ShieldCheck, ArrowRight } from 'lucide-react';

export interface PipelineStep {
  id: string;
  name: string;
  description: string;
  status: 'waiting' | 'active' | 'completed';
  progress?: number;
}

interface ProcessingFlowProps {
  steps: PipelineStep[];
  onViewResults?: () => void;
}

export const ProcessingFlow: React.FC<ProcessingFlowProps> = ({ steps, onViewResults }) => {
  const completedCount = steps.filter(s => s.status === 'completed').length;
  const isAllCompleted = completedCount === steps.length;
  const activeStep = steps.find(s => s.status === 'active');
  
  // Calculate total overall percentage
  const totalProgress = Math.min(
    100,
    Math.round(
      ((completedCount + (activeStep?.progress || 0) / 100) / steps.length) * 100
    )
  );

  return (
    <div className="bg-neutral-100 text-black border-2 border-dashed border-black/30 rounded-3xl p-8 shadow-sm w-full h-full flex flex-col justify-between overflow-y-auto select-none">
      <div>
        <div className="flex justify-between items-center border-b border-black/20 pb-4 mb-6">
          <div className="flex items-center space-x-4">
            {isAllCompleted ? (
              <ShieldCheck className="w-8 h-8 text-black" />
            ) : (
              <Loader2 className="w-8 h-8 text-black animate-spin" />
            )}
            <div>
              <h2 className="text-2xl font-orbitron font-bold tracking-widest text-black uppercase">
                {isAllCompleted ? "Pipeline Completed — All 7 Stages Passed" : "AI Inference Pipeline Execution"}
              </h2>
              <p className="text-xs font-mono text-black/60 mt-0.5">
                {isAllCompleted
                  ? "Analysis completed successfully. Click View Results to view dashboard."
                  : `Stage ${Math.min(steps.length, completedCount + (activeStep ? 1 : 0))} of ${steps.length}: ${activeStep?.name || "Processing"}`}
              </p>
            </div>
          </div>
          <div className="flex items-center space-x-4">
            <div className="text-right">
              <span className="font-orbitron font-bold text-2xl font-mono text-black block">
                {totalProgress}%
              </span>
              <span className="text-[10px] font-mono uppercase tracking-widest text-black/50">
                Total Progress
              </span>
            </div>
            {isAllCompleted && onViewResults && (
              <motion.button
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                onClick={onViewResults}
                className="py-3 px-5 bg-black text-white hover:bg-neutral-800 font-orbitron font-bold text-xs uppercase tracking-widest transition-all cursor-pointer flex items-center space-x-2 border-2 border-black rounded-2xl shadow-lg shrink-0"
              >
                <span>View Results</span>
                <ArrowRight className="w-4 h-4 text-white" />
              </motion.button>
            )}
          </div>
        </div>

        {/* Overall Progress Bar */}
        <div className="w-full bg-black/10 h-2 rounded-full mb-6 overflow-hidden border border-black/20">
          <div
            className="bg-black h-full transition-all duration-150 ease-out"
            style={{ width: `${totalProgress}%` }}
          />
        </div>

        <div className="flex flex-col space-y-3">
          <AnimatePresence>
            {steps.map((step) => {
              const isCompleted = step.status === 'completed';
              const isActive = step.status === 'active';

              if (isActive) {
                const currentPct = Math.round(step.progress || 0);
                return (
                  <motion.div
                    key={step.id}
                    initial={{ opacity: 0, y: 5 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="relative overflow-hidden bg-black text-white border-2 border-dashed border-black p-4 rounded-2xl shadow-md"
                  >
                    {/* Light container grey fill sweeping left to right as it progresses, replacing black */}
                    <div
                      className="absolute inset-y-0 left-0 bg-neutral-100 z-0 transition-all duration-75 ease-linear"
                      style={{ width: `${currentPct}%` }}
                    />

                    <div className="relative z-10 flex items-center justify-between mix-blend-difference text-white">
                      <div className="flex items-center space-x-4">
                        <Loader2 className="w-6 h-6 animate-spin flex-shrink-0" />
                        <div>
                          <h3 className="text-lg font-orbitron font-bold tracking-wider uppercase">
                            {step.name}
                          </h3>
                          <p className="text-sm font-mono mt-0.5 opacity-90">
                            {step.description}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center space-x-3 flex-shrink-0">
                        <span className="text-sm font-mono font-bold font-orbitron tracking-wider">
                          {currentPct}%
                        </span>
                        <span className="text-xs px-3 py-1 bg-white text-black rounded-full font-bold uppercase tracking-widest font-orbitron">
                          Processing
                        </span>
                      </div>
                    </div>
                  </motion.div>
                );
              }

              if (isCompleted) {
                return (
                  <motion.div
                    key={step.id}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="bg-transparent text-black border-2 border-dashed border-black/30 p-4 rounded-2xl flex items-center justify-between shadow-sm"
                  >
                    <div className="flex items-center space-x-4">
                      <CheckCircle2 className="w-6 h-6 text-black flex-shrink-0" />
                      <div>
                        <h3 className="text-lg font-orbitron font-bold tracking-wider uppercase text-black">
                          {step.name}
                        </h3>
                        <p className="text-sm font-mono mt-0.5 text-black/60">
                          {step.description}
                        </p>
                      </div>
                    </div>
                    <span className="text-xs px-3 py-1 bg-black text-white rounded-full font-bold uppercase tracking-widest font-orbitron flex-shrink-0">
                      Done
                    </span>
                  </motion.div>
                );
              }

              // Default Queued state - starts solid black!
              return (
                <div
                  key={step.id}
                  className="bg-black text-white border-2 border-dashed border-black p-4 rounded-2xl flex items-center justify-between shadow-sm"
                >
                  <div className="flex items-center space-x-4">
                    <Hourglass className="w-5 h-5 flex-shrink-0 text-white/70" />
                    <div>
                      <h3 className="text-base font-orbitron font-semibold tracking-wider uppercase text-white">
                        {step.name}
                      </h3>
                      <p className="text-xs font-mono mt-0.5 text-white/60">
                        {step.description}
                      </p>
                    </div>
                  </div>
                  <span className="text-[10px] px-2.5 py-0.5 border border-white/30 text-white/70 rounded-full font-orbitron uppercase tracking-wider">
                    Queued
                  </span>
                </div>
              );
            })}
          </AnimatePresence>
        </div>
      </div>

      <div className="pt-4 border-t border-black/10 flex justify-between items-center text-xs font-mono text-black/60 uppercase tracking-widest flex-shrink-0">
        <span>TESS Neural Engine v2.4</span>
        <span>{isAllCompleted ? "✓ All 7 Stages Validated" : "Executing Pipeline..."}</span>
      </div>
    </div>
  );
};

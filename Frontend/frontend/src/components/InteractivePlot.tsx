import React, { useState, useEffect, useMemo, useRef } from 'react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  AreaChart,
  Area,
  ReferenceLine,
  ReferenceDot
} from 'recharts';
import {
  Download,
  LineChart as ChartIcon,
  X,
  ZoomIn,
  Move,
  RotateCcw,
  ArrowUpDown,
  ChevronLeft,
  ChevronRight
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

interface InteractivePlotProps {
  originalCurve: { time: number; flux: number }[];
  detrendedCurve: { time: number; flux: number }[];
  periodogram: { period: number; power: number }[];
  foldedCurve: { phase: number; flux: number; model: number }[];
  bestPeriod?: number;
  bestPower?: number;
}

const PLOT_ORDER = ['Comparison', 'Raw', 'Detrended', 'Periodogram', 'Folded'];

const PLOT_TITLES: Record<string, string> = {
  Comparison: '1. Raw & Detrended Comparison View',
  Raw: '2. Raw Aperture Photometry',
  Detrended: '3. Detrended Light Curve',
  Periodogram: '4. BLS Power Spectrum',
  Folded: '5. Phase-Folded Fit Overlay'
};

const formatAxisTick = (val: any) => {
  if (typeof val === 'number' && !isNaN(val)) {
    const rounded = Math.round(val * 100) / 100;
    return String(rounded);
  }
  return val;
};

const formatTooltipValue = (val: any) => {
  if (typeof val === 'number' && !isNaN(val)) {
    // Strip trailing redundant zeros while keeping exact precision up to 8 decimal places
    const rounded = Math.round(val * 1e8) / 1e8;
    return String(rounded);
  }
  return val;
};

export const InteractivePlot: React.FC<InteractivePlotProps> = ({
  originalCurve,
  detrendedCurve,
  periodogram,
  foldedCurve,
  bestPeriod,
  bestPower
}) => {
  const [fullscreenPlot, setFullscreenPlot] = useState<string | null>(null);
  const [zoomDomain, setZoomDomain] = useState<{ x: [number, number]; y: [number, number] } | null>(null);
  const [detrendedZoomY, setDetrendedZoomY] = useState<[number, number] | null>(null);
  const [dragMode, setDragMode] = useState<'pan' | 'yscale' | null>(null);
  const [panStart, setPanStart] = useState<{ x: number; y: number } | null>(null);

  const rafRef = useRef<number | null>(null);

  // Reset zoom & pan when active detailed plot changes
  useEffect(() => {
    setZoomDomain(null);
    setDetrendedZoomY(null);
    setDragMode(null);
    setPanStart(null);
    if (rafRef.current) {
      cancelAnimationFrame(rafRef.current);
    }
  }, [fullscreenPlot]);

  // Keyboard navigation for cycling graphs in detailed modal
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!fullscreenPlot) return;
      if (e.key === 'ArrowLeft') {
        handlePrevPlot();
      } else if (e.key === 'ArrowRight') {
        handleNextPlot();
      } else if (e.key === 'Escape') {
        setFullscreenPlot(null);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [fullscreenPlot]);

  const handlePrevPlot = (e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    if (!fullscreenPlot) return;
    const currentIndex = PLOT_ORDER.indexOf(fullscreenPlot);
    const prevIndex = (currentIndex - 1 + PLOT_ORDER.length) % PLOT_ORDER.length;
    setFullscreenPlot(PLOT_ORDER[prevIndex]);
  };

  const handleNextPlot = (e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    if (!fullscreenPlot) return;
    const currentIndex = PLOT_ORDER.indexOf(fullscreenPlot);
    const nextIndex = (currentIndex + 1) % PLOT_ORDER.length;
    setFullscreenPlot(PLOT_ORDER[nextIndex]);
  };

  const handleDownload = (plotType: string) => {
    alert(`PNG download is simulated for the ${plotType} plot.`);
  };

  const getPlotDataAndKeys = (type: string | null) => {
    if (type === 'Comparison' || type === 'Raw') {
      return { data: originalCurve, xKey: 'time', yKeys: ['flux', 'baseline'] };
    }
    if (type === 'Detrended') return { data: detrendedCurve, xKey: 'time', yKeys: ['flux', 'model'] };
    if (type === 'Periodogram') return { data: periodogram, xKey: 'period', yKeys: ['power'] };
    if (type === 'Folded') return { data: foldedCurve, xKey: 'phase', yKeys: ['flux', 'model'] };
    return { data: [], xKey: '', yKeys: [] };
  };

  const initialBounds = useMemo(() => {
    if (!fullscreenPlot) return null;
    const { data, xKey, yKeys } = getPlotDataAndKeys(fullscreenPlot);
    if (!data || data.length === 0) return { x: [0, 1] as [number, number], y: [0, 1] as [number, number] };

    let minX = Infinity, maxX = -Infinity;
    let minY = Infinity, maxY = -Infinity;

    for (const pt of data) {
      const xVal = (pt as any)[xKey];
      if (typeof xVal === 'number' && !isNaN(xVal)) {
        if (xVal < minX) minX = xVal;
        if (xVal > maxX) maxX = xVal;
      }
      for (const yKey of yKeys) {
        const yVal = (pt as any)[yKey];
        if (typeof yVal === 'number' && !isNaN(yVal)) {
          if (yVal < minY) minY = yVal;
          if (yVal > maxY) maxY = yVal;
        }
      }
    }

    if (minX === Infinity) { minX = 0; maxX = 1; }
    if (minY === Infinity) { minY = 0; maxY = 1; }

    const xPad = (maxX - minX) * 0.02 || 0.1;
    const yPad = (maxY - minY) * 0.05 || 0.1;

    return {
      x: [minX - xPad, maxX + xPad] as [number, number],
      y: [minY - yPad, maxY + yPad] as [number, number]
    };
  }, [fullscreenPlot, originalCurve, detrendedCurve, periodogram, foldedCurve]);

  const initialDetrendedYBounds = useMemo(() => {
    if (!detrendedCurve || detrendedCurve.length === 0) return [0, 1] as [number, number];
    let minY = Infinity, maxY = -Infinity;
    for (const pt of detrendedCurve) {
      if (typeof pt.flux === 'number' && !isNaN(pt.flux)) {
        if (pt.flux < minY) minY = pt.flux;
        if (pt.flux > maxY) maxY = pt.flux;
      }
      const modelVal = (pt as any).model;
      if (typeof modelVal === 'number' && !isNaN(modelVal)) {
        if (modelVal < minY) minY = modelVal;
        if (modelVal > maxY) maxY = modelVal;
      }
    }
    if (minY === Infinity) { minY = 0.99; maxY = 1.01; }
    const yPad = (maxY - minY) * 0.08 || 0.005;
    return [minY - yPad, maxY + yPad] as [number, number];
  }, [detrendedCurve]);

  const activeDetrendedYDomain = detrendedZoomY || initialDetrendedYBounds;

  const handleWheel = (e: React.WheelEvent<HTMLDivElement>) => {
    if (!fullscreenPlot || !initialBounds) return;
    e.preventDefault();

    const container = e.currentTarget;
    const rect = container.getBoundingClientRect();

    const mouseXRatio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));

    const bounds = zoomDomain || initialBounds;
    const [xMin, xMax] = bounds.x;
    const [yMin, yMax] = bounds.y;

    const [initXMin, initXMax] = initialBounds.x;
    const maxSpanX = initXMax - initXMin;

    const spanX = xMax - xMin;
    const factor = e.deltaY < 0 ? 0.88 : 1.14;
    const newSpanX = spanX * factor;

    if (newSpanX >= maxSpanX) {
      setZoomDomain({
        x: [initXMin, initXMax],
        y: [yMin, yMax]
      });
      return;
    }

    const cursorX = xMin + mouseXRatio * spanX;
    let newXMin = cursorX - mouseXRatio * newSpanX;
    let newXMax = newXMin + newSpanX;

    if (newXMin < initXMin) {
      newXMin = initXMin;
      newXMax = newXMin + newSpanX;
    }
    if (newXMax > initXMax) {
      newXMax = initXMax;
      newXMin = newXMax - newSpanX;
    }

    setZoomDomain({
      x: [newXMin, newXMax],
      y: [yMin, yMax]
    });
  };

  const handleMouseDown = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!fullscreenPlot) return;
    if (e.button === 0) {
      setDragMode('pan');
      setPanStart({ x: e.clientX, y: e.clientY });
    } else if (e.button === 2) {
      e.preventDefault();
      setDragMode('yscale');
      setPanStart({ x: e.clientX, y: e.clientY });
    }
  };

  const handleContextMenu = (e: React.MouseEvent<HTMLDivElement>) => {
    e.preventDefault();
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!dragMode || !panStart || !fullscreenPlot || !initialBounds) return;

    const clientX = e.clientX;
    const clientY = e.clientY;
    const container = e.currentTarget;
    const rect = container.getBoundingClientRect();

    if (rafRef.current) {
      cancelAnimationFrame(rafRef.current);
    }

    rafRef.current = requestAnimationFrame(() => {
      const deltaPxX = clientX - panStart.x;
      const deltaPxY = clientY - panStart.y;

      if (Math.abs(deltaPxX) < 1 && Math.abs(deltaPxY) < 1) return;

      const bounds = zoomDomain || initialBounds;
      const [xMin, xMax] = bounds.x;
      const [yMin, yMax] = bounds.y;
      const [initXMin, initXMax] = initialBounds.x;

      if (dragMode === 'pan') {
        const spanX = xMax - xMin;
        const rawSpanY = yMax - yMin;
        const detSpanY = activeDetrendedYDomain[1] - activeDetrendedYDomain[0];

        const deltaDataX = (deltaPxX / rect.width) * spanX;
        const deltaRawY = (deltaPxY / rect.height) * rawSpanY;
        const deltaDetY = (deltaPxY / rect.height) * detSpanY;

        let newXMin = xMin - deltaDataX;
        let newXMax = xMax - deltaDataX;

        if (newXMin < initXMin) {
          newXMin = initXMin;
          newXMax = newXMin + spanX;
        }
        if (newXMax > initXMax) {
          newXMax = initXMax;
          newXMin = newXMax - spanX;
        }

        setZoomDomain({
          x: [newXMin, newXMax],
          y: [yMin + deltaRawY, yMax + deltaRawY]
        });

        setDetrendedZoomY([
          activeDetrendedYDomain[0] + deltaDetY,
          activeDetrendedYDomain[1] + deltaDetY
        ]);
      } else if (dragMode === 'yscale') {
        const scaleFactor = Math.pow(1.006, deltaPxY);

        const rawCenter = (yMin + yMax) / 2;
        const rawHalfSpan = (yMax - yMin) / 2;
        const newRawHalf = Math.max(1e-9, rawHalfSpan * scaleFactor);

        const detMin = activeDetrendedYDomain[0];
        const detMax = activeDetrendedYDomain[1];
        const detCenter = (detMin + detMax) / 2;
        const detHalfSpan = (detMax - detMin) / 2;
        const newDetHalf = Math.max(1e-9, detHalfSpan * scaleFactor);

        setZoomDomain({
          x: [xMin, xMax],
          y: [rawCenter - newRawHalf, rawCenter + newRawHalf]
        });

        setDetrendedZoomY([detCenter - newDetHalf, detCenter + newDetHalf]);
      }

      setPanStart({ x: clientX, y: clientY });
    });
  };

  const handleMouseUp = () => {
    setDragMode(null);
    setPanStart(null);
    if (rafRef.current) {
      cancelAnimationFrame(rafRef.current);
    }
  };

  const activeBounds = zoomDomain || initialBounds;
  const xDomain = activeBounds ? activeBounds.x : ['auto', 'auto'];
  const yDomain = activeBounds ? activeBounds.y : ['auto', 'auto'];

  return (
    <div className="space-y-6 w-full outline-none focus:outline-none select-none text-black">
      <div className="flex items-center space-x-3 border-b border-black/20 pb-4">
        <ChartIcon className="w-6 h-6 text-black stroke-[2]" />
        <h2 className="text-2xl font-orbitron font-bold tracking-widest text-black uppercase">Scientific Light Curve Analysis</h2>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* 1. MERGED COMPARISON GRAPH WINDOW */}
        <motion.div 
          layoutId="graph-card-Comparison"
          onClick={() => setFullscreenPlot("Comparison")}
          className="lg:col-span-2 bg-white border border-black/20 rounded-none p-6 shadow-xl flex flex-col justify-between cursor-pointer group transition-all duration-300 relative select-none outline-none focus:outline-none focus:ring-0 focus-visible:outline-none hover:-translate-y-0.5"
          style={{ outline: 'none' }}
        >
          <div className="flex justify-between items-center mb-4">
            <div className="flex items-center space-x-3">
              <span className="text-xs font-orbitron font-bold uppercase tracking-wider text-black">
                1. Raw & Detrended Comparison Window
              </span>
              <div className="flex items-center space-x-3 text-[10px] font-mono font-bold">
                <span className="text-[#38bdf8] flex items-center gap-1.5"><span className="w-2.5 h-2.5 bg-[#38bdf8] inline-block"></span> Raw</span>
                <span className="text-[#fb923c] flex items-center gap-1.5"><span className="w-2.5 h-2.5 bg-[#fb923c] inline-block"></span> Detrended</span>
              </div>
            </div>
            <div className="flex items-center space-x-1" onClick={(e) => e.stopPropagation()}>
              <button onClick={() => handleDownload("Comparison")} className="p-1.5 text-black/60 hover:text-black hover:bg-black/10 rounded-none transition-colors" title="Download PNG">
                <Download className="w-4 h-4" />
              </button>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 bg-gray-50 border border-black/10 rounded-none p-4 transition-colors">
            {/* Top Subplot: Raw Aperture Photometry */}
            <div>
              <div className="text-[10px] font-mono font-bold text-[#38bdf8] uppercase tracking-wider mb-1">
                ▲ Raw Aperture Photometry
              </div>
              <div className="flex flex-row items-stretch w-full h-[180px]">
                {/* Left Y-Axis Label Container */}
                <div 
                  className="flex items-center justify-center border-r border-black/10 px-2 mr-1 text-[#38bdf8] font-mono text-[10px] font-bold uppercase tracking-wider select-none shrink-0" 
                  style={{ writingMode: 'vertical-lr', transform: 'rotate(180deg)' }}
                >
                  Flux (e-/s)
                </div>
                <div className="flex-1 min-w-0 min-h-0 h-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart syncId="raw-detrended-comparison-grid" data={originalCurve} margin={{ top: 10, right: 10, left: 10, bottom: 15 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" horizontal={true} vertical={false} />
                      <XAxis dataKey="time" stroke="#000000" tick={{ fontSize: 9, fill: '#374151' }} tickFormatter={formatAxisTick} label={{ value: 'Time (BJD - 2457000)', position: 'insideBottom', offset: -10, fill: '#111827', fontSize: 9, fontWeight: 'bold' }} />
                      <YAxis width={65} stroke="#000000" tick={{ fontSize: 9, fill: '#374151' }} tickFormatter={formatAxisTick} domain={['auto', 'auto']} />
                      <Tooltip contentStyle={{ backgroundColor: '#ffffff', borderColor: '#000000', borderRadius: '0px', color: '#000000' }} labelStyle={{ color: '#000000', fontWeight: 'bold' }} labelFormatter={(l: any) => `Time: ${formatTooltipValue(l)}`} formatter={(val: any, name: any) => [formatTooltipValue(val), name]} />
                      <Legend verticalAlign="top" height={24} iconSize={9} wrapperStyle={{ fontSize: 9, fontWeight: 'bold', color: '#000000' }} />
                      <Line name="Raw Data" type="monotone" dataKey="flux" stroke="#38bdf8" dot={false} strokeWidth={1.2} isAnimationActive={false} />
                      <Line name="Baseline Trend" type="monotone" dataKey="baseline" stroke="#64748b" dot={false} strokeWidth={1.5} isAnimationActive={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>

            {/* Bottom Subplot: Detrended Light Curve */}
            <div className="border-t border-black/10 pt-3">
              <div className="text-[10px] font-mono font-bold text-[#fb923c] uppercase tracking-wider mb-1">
                ▼ Detrended Light Curve
              </div>
              <div className="flex flex-row items-stretch w-full h-[180px]">
                {/* Left Y-Axis Label Container */}
                <div 
                  className="flex items-center justify-center border-r border-black/10 px-2 mr-1 text-[#fb923c] font-mono text-[10px] font-bold uppercase tracking-wider select-none shrink-0" 
                  style={{ writingMode: 'vertical-lr', transform: 'rotate(180deg)' }}
                >
                  Detrended Flux
                </div>
                <div className="flex-1 min-w-0 min-h-0 h-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart syncId="raw-detrended-comparison-grid" data={detrendedCurve} margin={{ top: 10, right: 10, left: 10, bottom: 15 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" horizontal={true} vertical={false} />
                      <XAxis dataKey="time" stroke="#000000" tick={{ fontSize: 9, fill: '#374151' }} tickFormatter={formatAxisTick} label={{ value: 'Time (BJD - 2457000)', position: 'insideBottom', offset: -10, fill: '#111827', fontSize: 9, fontWeight: 'bold' }} />
                      <YAxis width={65} stroke="#000000" tick={{ fontSize: 9, fill: '#374151' }} tickFormatter={formatAxisTick} domain={['auto', 'auto']} />
                      <Tooltip contentStyle={{ backgroundColor: '#ffffff', borderColor: '#000000', borderRadius: '0px', color: '#000000' }} labelStyle={{ color: '#000000', fontWeight: 'bold' }} labelFormatter={(l: any) => `Time: ${formatTooltipValue(l)}`} formatter={(val: any, name: any) => [formatTooltipValue(val), name]} />
                      <Legend verticalAlign="top" height={24} iconSize={9} wrapperStyle={{ fontSize: 9, fontWeight: 'bold', color: '#000000' }} />
                      <Line name="Detrended Data" type="monotone" dataKey="flux" stroke="#fb923c" dot={false} strokeWidth={1.2} isAnimationActive={false} />
                      <Line name="Trapezoid Model" type="monotone" dataKey="model" stroke="#000000" dot={false} strokeWidth={1.5} isAnimationActive={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>
          </div>
        </motion.div>

        {/* 2. BLS Power Spectrum */}
        <motion.div 
          layoutId="graph-card-Periodogram"
          onClick={() => setFullscreenPlot("Periodogram")}
          className="bg-white border border-black/20 rounded-none p-6 shadow-xl flex flex-col justify-between cursor-pointer group transition-all duration-300 relative select-none outline-none focus:outline-none focus:ring-0 focus-visible:outline-none hover:-translate-y-0.5"
          style={{ outline: 'none' }}
        >
          <div className="flex justify-between items-start mb-4">
            <div>
              <span className="text-xs font-orbitron font-bold uppercase tracking-wider text-black block">
                2. BLS Power Spectrum
              </span>
              <span className="text-[10px] text-black/60 font-mono mt-0.5 block">
                Period Range: 0.5–15.0 days (12–360 hrs) | Grid: 6000 | Durations: 50
              </span>
            </div>
            <div className="flex items-center space-x-1" onClick={(e) => e.stopPropagation()}>
              <button onClick={() => handleDownload("Periodogram")} className="p-1.5 text-black/60 hover:text-black hover:bg-black/10 rounded-none transition-colors" title="Download PNG">
                <Download className="w-4 h-4" />
              </button>
            </div>
          </div>
          <div className="bg-gray-50 border border-black/10 rounded-none p-3 transition-colors">
            <div className="flex flex-row items-stretch w-full h-[320px]">
              {/* Left Y-Axis Label Container */}
              <div 
                className="flex items-center justify-center border-r border-black/10 px-2 mr-1 text-[#38bdf8] font-mono text-[10px] font-bold uppercase tracking-wider select-none shrink-0" 
                style={{ writingMode: 'vertical-lr', transform: 'rotate(180deg)' }}
              >
                BLS Power
              </div>
              <div className="flex-1 min-w-0 min-h-0 h-full">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={periodogram} margin={{ top: 20, right: 10, left: 10, bottom: 20 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" horizontal={true} vertical={false} />
                    <XAxis 
                      dataKey="period" 
                      type="number"
                      domain={[0.5, 15.0]}
                      ticks={[0.5, 2.0, 4.0, 6.0, 8.0, 10.0, 12.0, 15.0]}
                      stroke="#000000" 
                      tick={{ fontSize: 9, fill: '#374151' }} 
                      tickFormatter={formatAxisTick}
                      label={{ value: 'Trial Period (days)', position: 'insideBottom', offset: -12, fill: '#111827', fontSize: 10, fontWeight: 'bold' }} 
                    />
                    <YAxis width={60} stroke="#000000" tick={{ fontSize: 9, fill: '#374151' }} tickFormatter={formatAxisTick} />
                    <Tooltip contentStyle={{ backgroundColor: '#ffffff', borderColor: '#000000', borderRadius: '0px', color: '#000000' }} labelStyle={{ color: '#000000', fontWeight: 'bold' }} labelFormatter={(l: any) => `Period: ${formatTooltipValue(l)} d`} formatter={(val: any, name: any) => [formatTooltipValue(val), name]} />
                    {bestPeriod && (
                      <ReferenceLine 
                        x={bestPeriod} 
                        stroke="#000000" 
                        strokeDasharray="4 4" 
                        strokeWidth={1.5}
                        label={{ value: `Peak: ${bestPeriod.toFixed(4)} d`, fill: '#000000', fontSize: 10, position: 'top', fontWeight: 'bold' }} 
                      />
                    )}
                    {bestPeriod && bestPower && (
                      <ReferenceDot 
                        x={bestPeriod} 
                        y={bestPower} 
                        r={5} 
                        fill="#000000" 
                        stroke="#ffffff" 
                        strokeWidth={1.5}
                      />
                    )}
                    <Area type="monotone" dataKey="power" stroke="#38bdf8" fill="#38bdf8" fillOpacity={0.25} dot={false} isAnimationActive={false} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        </motion.div>

        {/* 3. Phase Folded Light Curve & Model */}
        <motion.div 
          layoutId="graph-card-Folded"
          onClick={() => setFullscreenPlot("Folded")}
          className="bg-white border border-black/20 rounded-none p-6 shadow-xl flex flex-col justify-between cursor-pointer group transition-all duration-300 relative select-none outline-none focus:outline-none focus:ring-0 focus-visible:outline-none hover:-translate-y-0.5"
          style={{ outline: 'none' }}
        >
          <div className="flex justify-between items-center mb-4">
            <span className="text-xs font-orbitron font-bold uppercase tracking-wider text-black">
              3. Phase-Folded Fit Overlay
            </span>
            <div className="flex items-center space-x-1" onClick={(e) => e.stopPropagation()}>
              <button onClick={() => handleDownload("Folded")} className="p-1.5 text-black/60 hover:text-black hover:bg-black/10 rounded-none transition-colors" title="Download PNG">
                <Download className="w-4 h-4" />
              </button>
            </div>
          </div>
          <div className="bg-gray-50 border border-black/10 rounded-none p-3 transition-colors">
            <div className="flex flex-row items-stretch w-full h-[320px]">
              {/* Left Y-Axis Label Container */}
              <div 
                className="flex items-center justify-center border-r border-black/10 px-2 mr-1 text-[#fb923c] font-mono text-[10px] font-bold uppercase tracking-wider select-none shrink-0" 
                style={{ writingMode: 'vertical-lr', transform: 'rotate(180deg)' }}
              >
                Normalized Flux
              </div>
              <div className="flex-1 min-w-0 min-h-0 h-full">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={foldedCurve} margin={{ top: 15, right: 10, left: 10, bottom: 20 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" horizontal={true} vertical={false} />
                    <XAxis dataKey="phase" stroke="#000000" tick={{ fontSize: 9, fill: '#374151' }} tickFormatter={formatAxisTick} label={{ value: 'Orbital Phase', position: 'insideBottom', offset: -12, fill: '#111827', fontSize: 10, fontWeight: 'bold' }} />
                    <YAxis width={60} stroke="#000000" tick={{ fontSize: 9, fill: '#374151' }} tickFormatter={formatAxisTick} domain={['auto', 'auto']} />
                    <Tooltip contentStyle={{ backgroundColor: '#ffffff', borderColor: '#000000', borderRadius: '0px', color: '#000000' }} labelStyle={{ color: '#000000', fontWeight: 'bold' }} labelFormatter={(l: any) => `Phase: ${formatTooltipValue(l)}`} formatter={(val: any, name: any) => [formatTooltipValue(val), name]} />
                    <Legend verticalAlign="top" height={32} iconSize={10} wrapperStyle={{ fontSize: 10, fontWeight: 'bold', color: '#000000' }} />
                    <Line name="Data" type="monotone" dataKey="flux" stroke="#fb923c" dot={{ r: 1.5, fill: '#fb923c' }} strokeWidth={0} isAnimationActive={false} />
                    <Line name="Trapezoid Model" type="monotone" dataKey="model" stroke="#000000" dot={false} strokeWidth={2.5} isAnimationActive={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        </motion.div>
      </div>

      {/* Detailed Scientific Plot Shared Element Layout Modal */}
      <AnimatePresence>
        {fullscreenPlot && (
          <motion.div
            layoutId={`graph-card-${fullscreenPlot}`}
            transition={{ type: 'spring', stiffness: 280, damping: 28 }}
            className="fixed inset-0 bg-white/95 text-black z-50 flex flex-col p-6 sm:p-8 justify-between select-none backdrop-blur-md outline-none focus:outline-none focus:ring-0 focus-visible:outline-none"
            style={{ outline: 'none' }}
          >
            {/* Modal Top Header with Title, Instructions, Cycle Arrow Buttons & Controls */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-4 border-b border-black/20 pb-4">
              <div className="flex items-center space-x-3">
                <ChartIcon className="w-6 h-6 text-black animate-pulse stroke-[2]" />
                <div>
                  <h2 className="text-2xl font-orbitron font-bold tracking-wider text-black uppercase flex items-center gap-3">
                    <span>{PLOT_TITLES[fullscreenPlot] || fullscreenPlot}</span>
                  </h2>
                  <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs font-mono text-black/60 mt-1">
                    <span className="flex items-center gap-1.5"><ZoomIn className="w-3.5 h-3.5 text-black/70" /> Scroll wheel to zoom</span>
                    <span className="flex items-center gap-1.5"><Move className="w-3.5 h-3.5 text-black/70" /> Left-click & drag to pan</span>
                    <span className="flex items-center gap-1.5"><ArrowUpDown className="w-3.5 h-3.5 text-black/70" /> Right-click & drag Y-scale</span>
                  </div>
                </div>
              </div>

              <div className="flex items-center space-x-3">
                {/* Graph Cycling Arrow Buttons */}
                <div className="flex items-center space-x-1 border border-black/30 bg-gray-100 p-1">
                  <button
                    onClick={handlePrevPlot}
                    className="p-1.5 hover:bg-black hover:text-white text-black transition-colors cursor-pointer"
                    title="Previous Graph (Left Arrow Key)"
                  >
                    <ChevronLeft className="w-5 h-5" />
                  </button>
                  <span className="text-[10px] font-mono px-2 text-black/70 font-bold uppercase">
                    {PLOT_ORDER.indexOf(fullscreenPlot) + 1} / {PLOT_ORDER.length}
                  </span>
                  <button
                    onClick={handleNextPlot}
                    className="p-1.5 hover:bg-black hover:text-white text-black transition-colors cursor-pointer"
                    title="Next Graph (Right Arrow Key)"
                  >
                    <ChevronRight className="w-5 h-5" />
                  </button>
                </div>

                {(zoomDomain || detrendedZoomY) && (
                  <button
                    onClick={() => { setZoomDomain(null); setDetrendedZoomY(null); }}
                    className="inline-flex items-center space-x-2 text-xs font-orbitron font-bold uppercase tracking-widest px-4 py-2.5 border border-black/40 text-black hover:bg-black hover:text-white rounded-none transition-colors cursor-pointer"
                    title="Reset Zoom & Pan to Original View"
                  >
                    <RotateCcw className="w-3.5 h-3.5" />
                    <span>Reset View</span>
                  </button>
                )}
                <button
                  onClick={() => handleDownload(fullscreenPlot)}
                  className="inline-flex items-center space-x-2 text-xs font-orbitron font-bold uppercase tracking-widest px-6 py-2.5 bg-black text-white hover:bg-neutral-800 rounded-none transition-colors cursor-pointer shadow-md"
                >
                  <Download className="w-4 h-4" />
                  <span>Export PNG</span>
                </button>
                <button
                  onClick={() => setFullscreenPlot(null)}
                  className="p-2 border border-black/20 hover:bg-black hover:text-white text-black rounded-none transition-colors cursor-pointer"
                  title="Exit Detailed View (ESC)"
                >
                  <X className="w-6 h-6" />
                </button>
              </div>
            </div>

            {/* Left and Right Overlay Screen Edge Arrows for Cycling */}
            <button
              onClick={handlePrevPlot}
              className="absolute left-3 top-1/2 -translate-y-1/2 z-30 p-3 bg-white border border-black/30 hover:border-black text-black hover:bg-black hover:text-white rounded-none transition-all shadow-2xl cursor-pointer group"
              title="Previous Graph (Left Arrow)"
            >
              <ChevronLeft className="w-7 h-7 group-hover:-translate-x-0.5 transition-transform" />
            </button>

            <button
              onClick={handleNextPlot}
              className="absolute right-3 top-1/2 -translate-y-1/2 z-30 p-3 bg-white border border-black/30 hover:border-black text-black hover:bg-black hover:text-white rounded-none transition-all shadow-2xl cursor-pointer group"
              title="Next Graph (Right Arrow)"
            >
              <ChevronRight className="w-7 h-7 group-hover:translate-x-0.5 transition-transform" />
            </button>

            {/* Main Interactive Plot Canvas Container */}
            <div 
              onWheel={handleWheel}
              onMouseDown={handleMouseDown}
              onMouseMove={handleMouseMove}
              onMouseUp={handleMouseUp}
              onMouseLeave={handleMouseUp}
              onContextMenu={handleContextMenu}
              className={`flex-1 bg-white border border-black/20 rounded-none p-4 px-12 flex flex-col justify-center min-h-0 relative outline-none focus:outline-none focus:ring-0 focus-visible:outline-none select-none ${
                dragMode === 'pan' ? 'cursor-grabbing' : dragMode === 'yscale' ? 'cursor-ns-resize' : 'cursor-grab'
              }`}
              style={{ outline: 'none' }}
            >
              {fullscreenPlot === 'Comparison' ? (
                /* Merged Raw & Detrended Comparison View (Stacked 2 Panels) */
                <div className="w-full h-full flex flex-col justify-between space-y-3 py-1">
                  {/* Top Panel: Raw Aperture Photometry */}
                  <div className="flex-1 w-full flex flex-col min-h-0 bg-gray-50 border border-black/10 p-3">
                    <div className="text-xs font-mono font-bold text-[#38bdf8] uppercase tracking-wider mb-1 flex items-center justify-between">
                      <span>▲ Raw Aperture Photometry</span>
                      <span className="text-[10px] text-black/60 font-normal">Flux (e-/s) vs Time (BJD)</span>
                    </div>
                    <div className="flex-1 min-h-0 w-full flex flex-row items-stretch">
                      {/* Separate Y-Axis Label Container */}
                      <div 
                        className="flex items-center justify-center border-r border-black/10 px-2.5 mr-2 text-[#38bdf8] font-mono text-[11px] font-bold uppercase tracking-wider select-none shrink-0" 
                        style={{ writingMode: 'vertical-lr', transform: 'rotate(180deg)' }}
                      >
                        Flux (e-/s)
                      </div>
                      <div className="flex-1 min-w-0 h-full">
                        <ResponsiveContainer width="100%" height="100%">
                          <LineChart syncId="raw-detrended-comparison-modal" data={originalCurve} margin={{ top: 10, right: 15, left: 10, bottom: 20 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" horizontal={true} vertical={false} />
                            <XAxis dataKey="time" type="number" domain={xDomain} allowDataOverflow={true} stroke="#000000" tick={{ fontSize: 10, fill: '#374151' }} tickFormatter={formatAxisTick} label={{ value: 'Time (BJD - 2457000)', position: 'insideBottom', offset: -12, fill: '#111827', fontSize: 11, fontWeight: 'bold' }} />
                            <YAxis width={65} type="number" domain={yDomain} allowDataOverflow={true} stroke="#000000" tick={{ fontSize: 10, fill: '#374151' }} tickFormatter={formatAxisTick} />
                            <Tooltip contentStyle={{ backgroundColor: '#ffffff', borderColor: '#000000', borderRadius: '0px', color: '#000000' }} labelStyle={{ color: '#000000', fontWeight: 'bold' }} labelFormatter={(l: any) => `Time: ${formatTooltipValue(l)}`} formatter={(val: any, name: any) => [formatTooltipValue(val), name]} />
                            <Legend verticalAlign="top" height={28} iconSize={12} wrapperStyle={{ fontSize: 11, fontWeight: 'bold', color: '#000000' }} />
                            <Line name="Raw Data" type="monotone" dataKey="flux" stroke="#38bdf8" dot={false} strokeWidth={1.5} isAnimationActive={false} />
                            <Line name="Baseline Trend" type="monotone" dataKey="baseline" stroke="#64748b" dot={false} strokeWidth={2} isAnimationActive={false} />
                          </LineChart>
                        </ResponsiveContainer>
                      </div>
                    </div>
                  </div>

                  {/* Bottom Panel: Detrended Light Curve */}
                  <div className="flex-1 w-full flex flex-col min-h-0 bg-gray-50 border border-black/10 p-3">
                    <div className="text-xs font-mono font-bold text-[#fb923c] uppercase tracking-wider mb-1 flex items-center justify-between">
                      <span>▼ Detrended Light Curve</span>
                      <span className="text-[10px] text-black/60 font-normal">Relative Flux vs Time (BJD)</span>
                    </div>
                    <div className="flex-1 min-h-0 w-full flex flex-row items-stretch">
                      {/* Separate Y-Axis Label Container */}
                      <div 
                        className="flex items-center justify-center border-r border-black/10 px-2.5 mr-2 text-[#fb923c] font-mono text-[11px] font-bold uppercase tracking-wider select-none shrink-0" 
                        style={{ writingMode: 'vertical-lr', transform: 'rotate(180deg)' }}
                      >
                        Detrended Flux
                      </div>
                      <div className="flex-1 min-w-0 h-full">
                        <ResponsiveContainer width="100%" height="100%">
                          <LineChart syncId="raw-detrended-comparison-modal" data={detrendedCurve} margin={{ top: 10, right: 15, left: 10, bottom: 20 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" horizontal={true} vertical={false} />
                            <XAxis dataKey="time" type="number" domain={xDomain} allowDataOverflow={true} stroke="#000000" tick={{ fontSize: 10, fill: '#374151' }} tickFormatter={formatAxisTick} label={{ value: 'Time (BJD - 2457000)', position: 'insideBottom', offset: -12, fill: '#111827', fontSize: 11, fontWeight: 'bold' }} />
                            <YAxis width={65} type="number" domain={activeDetrendedYDomain} allowDataOverflow={true} stroke="#000000" tick={{ fontSize: 10, fill: '#374151' }} tickFormatter={formatAxisTick} />
                            <Tooltip contentStyle={{ backgroundColor: '#ffffff', borderColor: '#000000', borderRadius: '0px', color: '#000000' }} labelStyle={{ color: '#000000', fontWeight: 'bold' }} labelFormatter={(l: any) => `Time: ${formatTooltipValue(l)}`} formatter={(val: any, name: any) => [formatTooltipValue(val), name]} />
                            <Legend verticalAlign="top" height={28} iconSize={12} wrapperStyle={{ fontSize: 11, fontWeight: 'bold', color: '#000000' }} />
                            <Line name="Detrended Data" type="monotone" dataKey="flux" stroke="#fb923c" dot={false} strokeWidth={1.5} isAnimationActive={false} />
                            <Line name="Trapezoid Model" type="monotone" dataKey="model" stroke="#000000" dot={false} strokeWidth={2} isAnimationActive={false} />
                          </LineChart>
                        </ResponsiveContainer>
                      </div>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="w-full h-full flex flex-row items-stretch">
                  {/* Separate Y-Axis Label Container */}
                  <div 
                    className="flex items-center justify-center border-r border-black/10 px-3 mr-3 font-mono text-xs font-bold uppercase tracking-wider select-none shrink-0" 
                    style={{ 
                      writingMode: 'vertical-lr', 
                      transform: 'rotate(180deg)',
                      color: fullscreenPlot === 'Raw' ? '#38bdf8' : fullscreenPlot === 'Detrended' || fullscreenPlot === 'Folded' ? '#fb923c' : '#38bdf8' 
                    }}
                  >
                    {fullscreenPlot === 'Raw' && 'Flux (e-/s)'}
                    {fullscreenPlot === 'Detrended' && 'Detrended Flux (Relative)'}
                    {fullscreenPlot === 'Periodogram' && 'BLS Power Spectrum'}
                    {fullscreenPlot === 'Folded' && 'Normalized Flux'}
                  </div>

                  <div className="flex-1 min-w-0 min-h-0 h-full">
                    <ResponsiveContainer width="100%" height="100%">
                      {fullscreenPlot === 'Raw' ? (
                        /* Single Raw Aperture Photometry */
                        <LineChart data={originalCurve} margin={{ top: 20, right: 20, left: 10, bottom: 25 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" horizontal={true} vertical={false} />
                          <XAxis dataKey="time" type="number" domain={xDomain} allowDataOverflow={true} stroke="#000000" tick={{ fontSize: 10, fill: '#374151' }} tickFormatter={formatAxisTick} label={{ value: 'Time (BJD - 2457000)', position: 'insideBottom', offset: -15, fill: '#111827', fontSize: 11, fontWeight: 'bold' }} />
                          <YAxis width={65} type="number" domain={yDomain} allowDataOverflow={true} stroke="#000000" tick={{ fontSize: 10, fill: '#374151' }} tickFormatter={formatAxisTick} />
                          <Tooltip contentStyle={{ backgroundColor: '#ffffff', borderColor: '#000000', borderRadius: '0px', color: '#000000' }} labelStyle={{ color: '#000000', fontWeight: 'bold' }} labelFormatter={(l: any) => `Time: ${formatTooltipValue(l)}`} formatter={(val: any, name: any) => [formatTooltipValue(val), name]} />
                          <Legend verticalAlign="top" height={32} iconSize={12} wrapperStyle={{ fontSize: 11, fontWeight: 'bold', color: '#000000' }} />
                          <Line name="Raw Photometry" type="monotone" dataKey="flux" stroke="#38bdf8" dot={false} strokeWidth={1.5} isAnimationActive={false} />
                          <Line name="Baseline Trend" type="monotone" dataKey="baseline" stroke="#64748b" dot={false} strokeWidth={2} isAnimationActive={false} />
                        </LineChart>
                      ) : fullscreenPlot === 'Detrended' ? (
                        /* Single Detrended Light Curve */
                        <LineChart data={detrendedCurve} margin={{ top: 20, right: 20, left: 10, bottom: 25 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" horizontal={true} vertical={false} />
                          <XAxis dataKey="time" type="number" domain={xDomain} allowDataOverflow={true} stroke="#000000" tick={{ fontSize: 10, fill: '#374151' }} tickFormatter={formatAxisTick} label={{ value: 'Time (BJD - 2457000)', position: 'insideBottom', offset: -15, fill: '#111827', fontSize: 11, fontWeight: 'bold' }} />
                          <YAxis width={65} type="number" domain={activeDetrendedYDomain} allowDataOverflow={true} stroke="#000000" tick={{ fontSize: 10, fill: '#374151' }} tickFormatter={formatAxisTick} />
                          <Tooltip contentStyle={{ backgroundColor: '#ffffff', borderColor: '#000000', borderRadius: '0px', color: '#000000' }} labelStyle={{ color: '#000000', fontWeight: 'bold' }} labelFormatter={(l: any) => `Time: ${formatTooltipValue(l)}`} formatter={(val: any, name: any) => [formatTooltipValue(val), name]} />
                          <Legend verticalAlign="top" height={32} iconSize={12} wrapperStyle={{ fontSize: 11, fontWeight: 'bold', color: '#000000' }} />
                          <Line name="Detrended Flux" type="monotone" dataKey="flux" stroke="#fb923c" dot={false} strokeWidth={1.5} isAnimationActive={false} />
                          <Line name="Trapezoid Model" type="monotone" dataKey="model" stroke="#000000" dot={false} strokeWidth={2} isAnimationActive={false} />
                        </LineChart>
                      ) : fullscreenPlot === 'Periodogram' ? (
                        /* Single BLS Power Spectrum */
                        <AreaChart data={periodogram} margin={{ top: 20, right: 20, left: 10, bottom: 25 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" horizontal={true} vertical={false} />
                          <XAxis dataKey="period" type="number" domain={xDomain} allowDataOverflow={true} stroke="#000000" tick={{ fontSize: 10, fill: '#374151' }} tickFormatter={formatAxisTick} label={{ value: 'Trial Period (days)', position: 'insideBottom', offset: -15, fill: '#111827', fontSize: 11, fontWeight: 'bold' }} />
                          <YAxis width={65} type="number" domain={yDomain} allowDataOverflow={true} stroke="#000000" tick={{ fontSize: 10, fill: '#374151' }} tickFormatter={formatAxisTick} />
                          <Tooltip contentStyle={{ backgroundColor: '#ffffff', borderColor: '#000000', borderRadius: '0px', color: '#000000' }} labelStyle={{ color: '#000000', fontWeight: 'bold' }} labelFormatter={(l: any) => `Period: ${formatTooltipValue(l)} d`} formatter={(val: any, name: any) => [formatTooltipValue(val), name]} />
                          {bestPeriod && (
                            <ReferenceLine x={bestPeriod} stroke="#000000" strokeDasharray="4 4" strokeWidth={2} label={{ value: `Best Period: ${bestPeriod.toFixed(4)} d`, fill: '#000000', fontSize: 11, position: 'top', fontWeight: 'bold' }} />
                          )}
                          {bestPeriod && bestPower && (
                            <ReferenceDot x={bestPeriod} y={bestPower} r={6} fill="#000000" stroke="#ffffff" strokeWidth={2} />
                          )}
                          <Area type="monotone" dataKey="power" stroke="#38bdf8" fill="#38bdf8" fillOpacity={0.3} dot={false} isAnimationActive={false} />
                        </AreaChart>
                      ) : (
                        /* Single Phase-Folded Light Curve */
                        <LineChart data={foldedCurve} margin={{ top: 20, right: 20, left: 10, bottom: 25 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" horizontal={true} vertical={false} />
                          <XAxis dataKey="phase" type="number" domain={xDomain} allowDataOverflow={true} stroke="#000000" tick={{ fontSize: 10, fill: '#374151' }} tickFormatter={formatAxisTick} label={{ value: 'Orbital Phase', position: 'insideBottom', offset: -15, fill: '#111827', fontSize: 11, fontWeight: 'bold' }} />
                          <YAxis width={65} type="number" domain={yDomain} allowDataOverflow={true} stroke="#000000" tick={{ fontSize: 10, fill: '#374151' }} tickFormatter={formatAxisTick} />
                          <Tooltip contentStyle={{ backgroundColor: '#ffffff', borderColor: '#000000', borderRadius: '0px', color: '#000000' }} labelStyle={{ color: '#000000', fontWeight: 'bold' }} labelFormatter={(l: any) => `Phase: ${formatTooltipValue(l)}`} formatter={(val: any, name: any) => [formatTooltipValue(val), name]} />
                          <Legend verticalAlign="top" height={32} iconSize={12} wrapperStyle={{ fontSize: 11, fontWeight: 'bold', color: '#000000' }} />
                          <Line name="Phase Data" type="monotone" dataKey="flux" stroke="#fb923c" dot={{ r: 2, fill: '#fb923c' }} strokeWidth={0} isAnimationActive={false} />
                          <Line name="Trapezoid Model" type="monotone" dataKey="model" stroke="#000000" dot={false} strokeWidth={3} isAnimationActive={false} />
                        </LineChart>
                      )}
                    </ResponsiveContainer>
                  </div>
                </div>
              )}
            </div>

            {/* Modal Bottom Footer Bar */}
            <div className="mt-4 border-t border-black/20 pt-3 flex flex-wrap justify-between items-center text-xs font-mono text-black/60 uppercase tracking-wider">
              <div>
                Target: <span className="text-black font-bold font-orbitron">TIC 251456988</span> | Sector 5 TESS High-Cadence Data
              </div>
              <div>
                Press <kbd className="px-2 py-0.5 bg-gray-200 border border-black/30 rounded-none text-black font-bold">ESC</kbd> or click Anywhere Outside to Exit Zoom
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

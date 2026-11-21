import React, { useState, useMemo } from 'react';
import { Sliders, LayoutGrid, Table, ArrowUpDown, ArrowUp, ArrowDown } from 'lucide-react';
import type { MetricItem } from '../utils/mockData';

interface MetricItemWithCategory extends MetricItem {
  category?: string;
}

interface MetricsGridProps {
  metrics: {
    bls: MetricItem[];
    transit: MetricItem[];
    physics: MetricItem[];
  };
}

export const MetricsGrid: React.FC<MetricsGridProps> = ({ metrics }) => {
  const [activeTab, setActiveTab] = useState<'bls' | 'transit' | 'physics' | 'all'>('bls');
  const [viewMode, setViewMode] = useState<'grid' | 'table'>('grid');

  // Sorting state for tabular view
  const [sortColumn, setSortColumn] = useState<'label' | 'value' | 'description' | 'category' | null>(null);
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');

  const tabs = [
    { id: 'bls', label: 'BLS Search' },
    { id: 'transit', label: 'Transit Parameters' },
    { id: 'physics', label: 'Physics Features' },
    { id: 'all', label: 'All Statistics' }
  ] as const;

  // Retrieve metrics with Category attached
  const currentMetrics: MetricItemWithCategory[] = useMemo(() => {
    const catMap: Record<string, string> = {
      bls: 'BLS Search',
      transit: 'Transit Parameters',
      physics: 'Physics Features'
    };

    if (activeTab === 'all') {
      return [
        ...(metrics.bls || []).map(item => ({ ...item, category: 'BLS Search' })),
        ...(metrics.transit || []).map(item => ({ ...item, category: 'Transit Parameters' })),
        ...(metrics.physics || []).map(item => ({ ...item, category: 'Physics Features' }))
      ];
    }
    return (metrics[activeTab] || []).map(item => ({
      ...item,
      category: catMap[activeTab]
    }));
  }, [activeTab, metrics]);

  // Handle column header click for sorting
  const handleSort = (column: 'label' | 'value' | 'description' | 'category') => {
    if (sortColumn === column) {
      if (sortDirection === 'asc') {
        setSortDirection('desc');
      } else {
        setSortColumn(null);
        setSortDirection('asc');
      }
    } else {
      setSortColumn(column);
      setSortDirection('asc');
    }
  };

  // Sorted list of metrics
  const sortedMetrics = useMemo(() => {
    if (!sortColumn) return currentMetrics;

    return [...currentMetrics].sort((a, b) => {
      const rawA = a[sortColumn] ? String(a[sortColumn]).trim() : '';
      const rawB = b[sortColumn] ? String(b[sortColumn]).trim() : '';

      // Try numeric comparison if applicable
      const numA = parseFloat(rawA);
      const numB = parseFloat(rawB);

      if (!isNaN(numA) && !isNaN(numB)) {
        return sortDirection === 'asc' ? numA - numB : numB - numA;
      }

      const strA = rawA.toLowerCase();
      const strB = rawB.toLowerCase();

      if (strA < strB) return sortDirection === 'asc' ? -1 : 1;
      if (strA > strB) return sortDirection === 'asc' ? 1 : -1;
      return 0;
    });
  }, [currentMetrics, sortColumn, sortDirection]);

  // Helper function to return colored border no-fill badge styles for metric titles
  const getBadgeStyle = (category?: string) => {
    if (category === 'BLS Search' || activeTab === 'bls') {
      return 'border-2 border-[#38bdf8] bg-transparent text-black';
    }
    if (category === 'Transit Parameters' || activeTab === 'transit') {
      return 'border-2 border-[#fb923c] bg-transparent text-black';
    }
    return 'border-2 border-black bg-transparent text-black';
  };

  return (
    <div className="bg-white border border-black/20 rounded-none p-6 shadow-xl w-full text-black">
      {/* Section Heading - ADDITIONAL STATISTICS + Grid/Table Switch */}
      <div className="flex flex-wrap justify-between items-center border-b border-black/20 pb-4 mb-6 gap-4">
        <div className="flex items-center space-x-3">
          <Sliders className="w-6 h-6 text-black stroke-[2]" />
          <h2 className="text-2xl font-orbitron font-bold tracking-[1.2px] text-black uppercase">
            ADDITIONAL STATISTICS
          </h2>
        </div>

        {/* View Mode Switcher */}
        <div className="flex items-center space-x-1 border border-black/20 p-1 bg-gray-100">
          <button
            type="button"
            onClick={() => setViewMode('grid')}
            className={`p-1.5 transition-colors cursor-pointer rounded-none flex items-center space-x-1.5 text-xs font-orbitron font-bold uppercase ${viewMode === 'grid'
                ? 'bg-black text-white shadow'
                : 'text-black/60 hover:text-black'
              }`}
            title="Grid View"
          >
            <LayoutGrid className="w-4 h-4" />
            <span className="hidden sm:inline">Grid</span>
          </button>
          <button
            type="button"
            onClick={() => setViewMode('table')}
            className={`p-1.5 transition-colors cursor-pointer rounded-none flex items-center space-x-1.5 text-xs font-orbitron font-bold uppercase ${viewMode === 'table'
                ? 'bg-black text-white shadow'
                : 'text-black/60 hover:text-black'
              }`}
            title="Tabular View"
          >
            <Table className="w-4 h-4" />
            <span className="hidden sm:inline">Table</span>
          </button>
        </div>
      </div>

      {/* Tabs list (including 'All Statistics') */}
      <div className="flex flex-wrap border-b border-black/20 mb-6 gap-2">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setActiveTab(tab.id)}
            className={`text-xs uppercase tracking-widest font-orbitron font-bold px-6 py-3 transition-all duration-300 cursor-pointer rounded-none ${activeTab === tab.id
                ? 'bg-black text-white shadow-lg'
                : 'text-black/60 hover:text-black border border-transparent hover:border-black/30'
              }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {viewMode === 'grid' ? (
        /* Grid View */
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {sortedMetrics.map((item, index) => (
            <div
              key={`${item.label}-${index}`}
              className="bg-gray-50 border border-black/20 rounded-none p-5 flex flex-col justify-between hover:border-black/60 transition-all duration-200"
            >
              <div>
                <div className={`${getBadgeStyle(item.category)} px-2.5 py-1 font-mono font-bold text-[10px] sm:text-xs tracking-[1px] uppercase inline-block mb-3 rounded-none`}>
                  {item.label}
                </div>
                <div className="text-xl font-orbitron font-bold text-black break-words">
                  {item.value}
                </div>
              </div>
              <div>
                <p className="text-xs text-black/60 mt-4 border-t border-black/10 pt-2 font-mono">
                  {item.description}
                </p>
                {item.category && (
                  <div className="text-[9px] text-black/40 font-mono uppercase tracking-wider mt-1.5">
                    Type: {item.category}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      ) : (
        /* Tabular View with Sorting */
        <div className="bg-white border border-black/20 rounded-none overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-black/20 bg-gray-100 text-[10px] uppercase font-orbitron tracking-widest text-black/70 font-bold select-none">
                <th
                  onClick={() => handleSort('label')}
                  className="py-4 px-6 w-1/4 cursor-pointer hover:bg-gray-200 transition-colors"
                >
                  <div className="flex items-center space-x-2">
                    <span>Metric</span>
                    {sortColumn === 'label' ? (
                      sortDirection === 'asc' ? <ArrowUp className="w-3 h-3 text-black" /> : <ArrowDown className="w-3 h-3 text-black" />
                    ) : (
                      <ArrowUpDown className="w-3 h-3 opacity-40 hover:opacity-100" />
                    )}
                  </div>
                </th>
                <th
                  onClick={() => handleSort('value')}
                  className="py-4 px-6 w-1/5 cursor-pointer hover:bg-gray-200 transition-colors"
                >
                  <div className="flex items-center space-x-2">
                    <span>Value</span>
                    {sortColumn === 'value' ? (
                      sortDirection === 'asc' ? <ArrowUp className="w-3 h-3 text-black" /> : <ArrowDown className="w-3 h-3 text-black" />
                    ) : (
                      <ArrowUpDown className="w-3 h-3 opacity-40 hover:opacity-100" />
                    )}
                  </div>
                </th>
                <th
                  onClick={() => handleSort('description')}
                  className="py-4 px-6 w-2/5 cursor-pointer hover:bg-gray-200 transition-colors"
                >
                  <div className="flex items-center space-x-2">
                    <span>Description</span>
                    {sortColumn === 'description' ? (
                      sortDirection === 'asc' ? <ArrowUp className="w-3 h-3 text-black" /> : <ArrowDown className="w-3 h-3 text-black" />
                    ) : (
                      <ArrowUpDown className="w-3 h-3 opacity-40 hover:opacity-100" />
                    )}
                  </div>
                </th>
                <th
                  onClick={() => handleSort('category')}
                  className="py-4 px-6 w-1/5 cursor-pointer hover:bg-gray-200 transition-colors"
                >
                  <div className="flex items-center space-x-2">
                    <span>Type</span>
                    {sortColumn === 'category' ? (
                      sortDirection === 'asc' ? <ArrowUp className="w-3 h-3 text-black" /> : <ArrowDown className="w-3 h-3 text-black" />
                    ) : (
                      <ArrowUpDown className="w-3 h-3 opacity-40 hover:opacity-100" />
                    )}
                  </div>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-black/10 text-xs font-semibold">
              {sortedMetrics.map((item, index) => (
                <tr key={`${item.label}-${index}`} className="hover:bg-gray-50 transition-colors">
                  <td className="py-4 px-6">
                    <span className={`${getBadgeStyle(item.category)} px-2.5 py-1 font-mono font-bold text-[10px] sm:text-xs tracking-[1px] uppercase inline-block rounded-none`}>
                      {item.label}
                    </span>
                  </td>
                  <td className="py-4 px-6 font-orbitron font-bold text-base text-black">
                    {item.value}
                  </td>
                  <td className="py-4 px-6 font-mono text-black/70 text-xs leading-relaxed">
                    {item.description}
                  </td>
                  <td className="py-4 px-6 font-mono text-black/50 text-xs">
                    {item.category}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

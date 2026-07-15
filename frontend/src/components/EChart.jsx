import { useEffect, useRef } from 'react';
import * as echarts from 'echarts/core';
import { BarChart, GraphChart, LineChart, LinesChart, PieChart, ScatterChart, TreemapChart } from 'echarts/charts';
import {
  GridComponent,
  LegendComponent,
  MarkAreaComponent,
  MarkLineComponent,
  MarkPointComponent,
  TitleComponent,
  TooltipComponent,
} from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';

echarts.use([
  BarChart,
  GraphChart,
  GridComponent,
  LegendComponent,
  LineChart,
  LinesChart,
  MarkAreaComponent,
  MarkLineComponent,
  MarkPointComponent,
  PieChart,
  ScatterChart,
  TitleComponent,
  TreemapChart,
  TooltipComponent,
  CanvasRenderer,
]);

export default function EChart({ option, className = '', style, onReady }) {
  const chartRef = useRef(null);
  const instanceRef = useRef(null);

  useEffect(() => {
    if (!chartRef.current) return undefined;
    instanceRef.current = echarts.init(chartRef.current, null, { renderer: 'canvas' });
    onReady?.(instanceRef.current);

    const handleResize = () => instanceRef.current?.resize();
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      onReady?.(null);
      instanceRef.current?.dispose();
      instanceRef.current = null;
    };
  }, [onReady]);

  useEffect(() => {
    if (instanceRef.current && option) {
      instanceRef.current.setOption(option, true);
    }
  }, [option]);

  return <div ref={chartRef} className={`chart ${className}`} style={style} />;
}

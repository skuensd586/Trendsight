import { useEffect, useRef } from 'react';
import * as echarts from 'echarts/core';
import { BarChart, EffectScatterChart, GraphChart, LineChart, MapChart, PieChart, SankeyChart, ScatterChart, ThemeRiverChart, TreemapChart } from 'echarts/charts';
import {
  GeoComponent,
  GridComponent,
  LegendComponent,
  MarkAreaComponent,
  MarkLineComponent,
  MarkPointComponent,
  SingleAxisComponent,
  TitleComponent,
  TimelineComponent,
  TooltipComponent,
  VisualMapComponent,
} from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import chinaGeo from '../data/chinaGeo.json';

echarts.use([
  BarChart,
  EffectScatterChart,
  GeoComponent,
  GraphChart,
  GridComponent,
  LegendComponent,
  LineChart,
  MapChart,
  MarkAreaComponent,
  MarkLineComponent,
  MarkPointComponent,
  PieChart,
  SankeyChart,
  ScatterChart,
  SingleAxisComponent,
  TitleComponent,
  TimelineComponent,
  ThemeRiverChart,
  TreemapChart,
  TooltipComponent,
  VisualMapComponent,
  CanvasRenderer,
]);

echarts.registerMap('china', chinaGeo);

export default function EChart({ option, className = '', style }) {
  const chartRef = useRef(null);
  const instanceRef = useRef(null);

  useEffect(() => {
    if (!chartRef.current) return undefined;
    instanceRef.current = echarts.init(chartRef.current, null, { renderer: 'canvas' });

    const handleResize = () => instanceRef.current?.resize();
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      instanceRef.current?.dispose();
      instanceRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (instanceRef.current && option) {
      instanceRef.current.setOption(option, true);
    }
  }, [option]);

  return <div ref={chartRef} className={`chart ${className}`} style={style} />;
}

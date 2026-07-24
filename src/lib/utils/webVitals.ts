// Web Vitals reporting utility
// Can be extended to send metrics to analytics endpoint
type MetricName = 'CLS' | 'FID' | 'LCP' | 'FCP' | 'TTFB' | 'INP';

interface Metric {
  name: MetricName;
  value: number;
  rating: string;
  delta: number;
  navigationType: string;
}

function reportMetric(metric: Metric): void {
  if (typeof console !== 'undefined') {
    console.log(`[WebVitals] ${metric.name}: ${metric.value} (${metric.rating})`);
  }
}

export function initWebVitals(): void {
  if (typeof window === 'undefined') return;

  // Dynamically import web-vitals when available
  import('web-vitals')
    .then(({ onCLS, onFID, onLCP, onFCP, onTTFB, onINP }) => {
      onCLS(reportMetric);
      onFID(reportMetric);
      onLCP(reportMetric);
      onFCP(reportMetric);
      onTTFB(reportMetric);
      onINP(reportMetric);
    })
    .catch(() => {
      // web-vitals not available — graceful fallback
    });
}

export type { Metric, MetricName };

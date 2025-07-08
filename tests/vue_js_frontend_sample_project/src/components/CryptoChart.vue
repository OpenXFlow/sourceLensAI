<template>
  <div class="chart-container">
    <Line :data="chartDataFormatted" :options="chartOptions" />
  </div>
</template>

<script>
import { Line } from 'vue-chartjs';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
);

export default {
  name: 'CryptoChart',
  components: { Line },
  props: {
    chartData: {
      type: Array,
      required: true,
    },
    coinId: {
      type: String,
      required: true,
    }
  },
  computed: {
    chartDataFormatted() {
      const labels = this.chartData.map(dataPoint => 
        new Date(dataPoint[0]).toLocaleDateString()
      );
      const data = this.chartData.map(dataPoint => dataPoint[1]);

      return {
        labels: labels,
        datasets: [
          {
            label: `Price (USD) for ${this.coinId}`,
            backgroundColor: '#f87979',
            borderColor: '#f87979',
            data: data,
            fill: false,
            tension: 0.1,
          },
        ],
      };
    },
    chartOptions() {
      return {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: true,
          },
          title: {
            display: true,
            text: `Last 30 Days Price Chart for ${this.coinId}`,
          },
        },
        scales: {
          y: {
            ticks: {
              callback: function(value) {
                return '$' + value.toLocaleString();
              }
            }
          }
        }
      };
    },
  },
};
</script>

<style scoped>
.chart-container {
  position: relative;
  height: 400px;
  width: 100%;
}
</style>
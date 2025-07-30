// admin charts

document.addEventListener('DOMContentLoaded', () => {
  // Expect a global `chartData` variable defined before this file is included
  if (!window.chartData) return;

  const ctx = document
    .getElementById('revenueChart')
    .getContext('2d');

  new Chart(ctx, {
    type: 'pie',
    data: {
      labels: chartData.labels,
      datasets: [{
        data: chartData.revenues,
        // Chart.js will pick default colors
      }]
    },
    options: {
      responsive: false,
      plugins: {
        legend: {
          position: 'bottom',
          labels: { boxWidth: 10, padding: 10 }
        }
      }
    }
  });
});
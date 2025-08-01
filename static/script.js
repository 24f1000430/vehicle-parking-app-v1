function renderAdminCharts({
  revenueLabels, revenueData, occupancyLabels, occupancyData
}) {
  // Revenue Pie Chart
  if (document.getElementById('revenueChart')) {
    new Chart(document.getElementById('revenueChart'), {
      type: 'pie',
      data: {
        labels: revenueLabels,
        datasets: [{
          data: revenueData,
          backgroundColor: [
            '#4e73df', '#1cc88a', '#36b9cc', '#f6c23e', '#e74a3b', '#858796', '#5a5c69'
          ],
        }]
      },
      options: {
        responsive: false,
        plugins: { legend: { display: true, position: 'bottom' } }
      }
    });
  }

  // Occupancy Line Chart
  if (document.getElementById('occupancyChart')) {
    new Chart(document.getElementById('occupancyChart'), {
      type: 'line',
      data: {
        labels: occupancyLabels,
        datasets: [{
          label: 'Occupancy %',
          data: occupancyData,
          borderColor: '#36b9cc',
          backgroundColor: 'rgba(54,185,204,0.2)',
          fill: true,
          tension: 0.4
        }]
      },
      options: {
        responsive: false,
        plugins: { legend: { display: false } },
        scales: {
          y: { min: 0, max: 100, title: { display: true, text: 'Occupancy (%)' } }
        }
      }
    });
  }
}

function renderUserCharts({
  usageLabels, usageData, paymentLabels, paymentData
}) {
  // Usage Pie Chart
  if (document.getElementById('usageChart')) {
    new Chart(document.getElementById('usageChart'), {
      type: 'pie',
      data: {
        labels: usageLabels,
        datasets: [{
          data: usageData,
          backgroundColor: [
            '#4e73df', '#1cc88a', '#36b9cc', '#f6c23e', '#e74a3b', '#858796', '#5a5c69'
          ],
        }]
      },
      options: {
        responsive: false,
        plugins: { legend: { display: true, position: 'bottom' } }
      }
    });
  }

  // Payments Doughnut Chart
  if (document.getElementById('paymentsChart')) {
    new Chart(document.getElementById('paymentsChart'), {
      type: 'doughnut',
      data: {
        labels: paymentLabels,
        datasets: [{
          data: paymentData,
          backgroundColor: ['#1cc88a', '#e74a3b'],
        }]
      },
      options: {
        responsive: false,
        plugins: { legend: { display: true, position: 'bottom' } }
      }
    });
  }
}

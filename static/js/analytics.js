// Submission Timeline Chart
var ctx = document.getElementById('submissionChart').getContext('2d');
var submissionChart = new Chart(ctx, {
    type: 'line',
    data: {
        labels: submissionData.labels,
        datasets: [{
            label: 'Submissions',
            data: submissionData.counts,
            borderColor: 'rgb(75, 192, 192)',
            tension: 0.1
        }]
    },
    options: {
        responsive: true,
        scales: {
            y: {
                beginAtZero: true
            }
        }
    }
});

// Course Completion Rates Chart
var ctx2 = document.getElementById('completionChart').getContext('2d');
var completionChart = new Chart(ctx2, {
    type: 'bar',
    data: {
        labels: completionData.labels,
        datasets: [{
            label: 'Completion Rate (%)',
            data: completionData.rates,
            backgroundColor: 'rgba(75, 192, 192, 0.6)'
        }]
    },
    options: {
        responsive: true,
        scales: {
            y: {
                beginAtZero: true,
                max: 100
            }
        }
    }
});
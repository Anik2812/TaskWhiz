document.addEventListener('DOMContentLoaded', function () {
    // Common elements
    const themeToggle = document.getElementById('theme-toggle');
    const loadingSpinner = document.getElementById('loading');
    const notificationContainer = document.getElementById('notification-container');

    // Page-specific elements
    const assignmentCards = document.querySelectorAll('.assignment-card');
    const courseFilter = document.getElementById('course-filter');
    const statusFilter = document.getElementById('status-filter');
    const sortFilter = document.getElementById('sort-filter');
    const assignmentsGrid = document.getElementById('assignments');
    const timeZoneSelect = document.getElementById('time_zone');
    const showGithubTokenBtn = document.getElementById('show-github-token');
    const deleteAccountBtn = document.getElementById('delete-account');
    const deleteAccountModal = document.getElementById('delete-account-modal');
    const analyticsContainer = document.getElementById('analytics-container');

    // Theme toggle functionality
    function setupThemeToggle() {
        if (themeToggle) {
            themeToggle.addEventListener('click', function (e) {
                e.preventDefault();
                document.body.classList.toggle('dark-theme');
                const icon = this.querySelector('i');
                if (icon.classList.contains('fa-moon')) {
                    icon.classList.replace('fa-moon', 'fa-sun');
                } else {
                    icon.classList.replace('fa-sun', 'fa-moon');
                }
                localStorage.setItem('theme', document.body.classList.contains('dark-theme') ? 'dark' : 'light');
            });
        }
    }

    function applyTheme() {
        const savedTheme = localStorage.getItem('theme');
        if (savedTheme === 'dark') {
            document.body.classList.add('dark-theme');
            const icon = document.querySelector('#theme-toggle i');
            if (icon) {
                icon.classList.replace('fa-moon', 'fa-sun');
            }
        }
    }

    // Loading spinner functions
    function showLoadingSpinner() {
        if (loadingSpinner) loadingSpinner.style.display = 'flex';
    }

    function hideLoadingSpinner() {
        if (loadingSpinner) loadingSpinner.style.display = 'none';
    }

    // Notification function
    function showNotification(message, type) {
        const notificationContainer = document.getElementById('notification-container');
        if (!notificationContainer) {
            console.error('Notification container not found');
            return;
        }

        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.textContent = message;
        notificationContainer.appendChild(notification);

        setTimeout(() => {
            notification.classList.add('show');
        }, 100);

        setTimeout(() => {
            notification.classList.remove('show');
            setTimeout(() => {
                notification.remove();
            }, 300);
        }, 3000);
    }

    // Assignment card functionality
    function setupAssignmentCards() {
        if (assignmentCards.length > 0) {
            assignmentCards.forEach(card => {
                card.addEventListener('mouseenter', function () {
                    this.style.transform = 'scale(1.05)';
                    this.style.boxShadow = '0 10px 20px rgba(0, 0, 0, 0.2)';
                });
                card.addEventListener('mouseleave', function () {
                    this.style.transform = 'scale(1)';
                    this.style.boxShadow = '0 4px 6px rgba(0, 0, 0, 0.1)';
                });
            });

            // View Details functionality
            document.querySelectorAll('.view-details').forEach(button => {
                button.addEventListener('click', function () {
                    const assignmentId = this.getAttribute('data-assignment-id');
                    fetchAssignmentDetails(assignmentId);
                });
            });

            // Submit Assignment functionality
            document.querySelectorAll('.submit-form').forEach(form => {
                form.addEventListener('submit', function (e) {
                    e.preventDefault();
                    const assignmentId = this.querySelector('.submit-btn').getAttribute('data-assignment-id');
                    const fileInput = this.querySelector('.file-input');

                    if (!fileInput || fileInput.files.length === 0) {
                        showNotification('Please select a file to upload.', 'error');
                        return;
                    }

                    const formData = new FormData(this);
                    formData.append('assignment_id', assignmentId);

                    submitAssignment(formData);
                });
            });

            // File input change event
            document.querySelectorAll('.file-input').forEach(input => {
                input.addEventListener('change', function (e) {
                    const fileName = e.target.files[0].name;
                    const assignmentId = this.dataset.assignmentId;
                    const label = document.querySelector(`label[for="file-${assignmentId}"]`);
                    if (label) {
                        label.innerHTML = `<i class="fas fa-file"></i> ${fileName}`;
                        label.classList.add('file-selected');
                    }
                });
            });
        }
    }

    // Fetch assignment details
    function fetchAssignmentDetails(assignmentId) {
        showLoadingSpinner();
        fetch(`/assignment/${assignmentId}`)
            .then(response => response.json())
            .then(data => {
                hideLoadingSpinner();
                if (data.success) {
                    displayAssignmentDetails(data.assignment);
                } else {
                    showNotification(data.message || 'Error fetching assignment details.', 'error');
                }
            })
            .catch(error => {
                hideLoadingSpinner();
                console.error('Error:', error);
                showNotification('An error occurred while fetching assignment details.', 'error');
            });
    }

    // Display assignment details
    function displayAssignmentDetails(assignment) {
        let modal = document.getElementById('assignment-details-modal');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'assignment-details-modal';
            modal.className = 'modal';
            document.body.appendChild(modal);
        }

        const detailsHtml = `
            <div class="modal-content">
                <span class="close">&times;</span>
                <h2>${assignment.title}</h2>
                <p><strong>Course:</strong> ${assignment.course}</p>
                <p><strong>Due Date:</strong> ${formatDate(assignment.due_date)}</p>
                <p><strong>Status:</strong> ${assignment.status}</p>
                <p><strong>Description:</strong> ${assignment.description}</p>
                ${assignment.file_url ? `<p><strong>Attached File:</strong> <a href="${assignment.file_url}" target="_blank">View File</a></p>` : ''}
                ${assignment.status === 'Graded' ? `<p><strong>Grade:</strong> ${assignment.grade} / ${assignment.total_marks}</p>` : ''}
                ${assignment.feedback ? `<p><strong>Feedback:</strong> ${assignment.feedback}</p>` : ''}
            </div>
        `;

        modal.innerHTML = detailsHtml;
        modal.style.display = 'block';

        const closeSpan = modal.querySelector('.close');
        closeSpan.onclick = function () {
            modal.style.display = 'none';
        }

        window.onclick = function (event) {
            if (event.target == modal) {
                modal.style.display = 'none';
            }
        }

        document.addEventListener('keydown', function (event) {
            if (event.key === 'Escape' && modal.style.display === 'block') {
                modal.style.display = 'none';
            }
        });
    }

    // Helper function to format date
    function formatDate(dateString) {
        const options = { year: 'numeric', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit' };
        return new Date(dateString).toLocaleDateString(undefined, options);
    }

    // Submit assignment
    function submitAssignment(formData) {
        showLoadingSpinner();
        fetch('/submit_assignment', {
            method: 'POST',
            body: formData
        })
            .then(response => response.json())
            .then(data => {
                hideLoadingSpinner();
                if (data.success) {
                    showNotification('Assignment submitted successfully!', 'success');
                    updateAssignmentStatus(data.assignment_id, 'Submitted');
                } else {
                    showNotification(data.message || 'Error submitting assignment. Please try again.', 'error');
                }
            })
            .catch(error => {
                hideLoadingSpinner();
                console.error('Error:', error);
                showNotification('An error occurred. Please try again.', 'error');
            });
    }

    // Update assignment status
    function updateAssignmentStatus(assignmentId, status) {
        const assignmentCard = document.querySelector(`.assignment-card[data-assignment-id="${assignmentId}"]`);
        if (assignmentCard) {
            const statusElement = assignmentCard.querySelector('.assignment-status');
            const cardActions = assignmentCard.querySelector('.card-actions');

            statusElement.innerHTML = `<i class="fas fa-circle"></i> ${status}`;
            statusElement.className = `assignment-status status-${status.toLowerCase().replace(' ', '-')}`;

            if (status === 'Submitted') {
                cardActions.innerHTML = `
                    <button class="btn btn-secondary open-assignment" data-assignment-id="${assignmentId}">
                        <i class="fas fa-folder-open"></i> Open
                    </button>
                `;
            }
        }
    }

    // Filter and sort assignments
    function applyFiltersAndSort() {
        const assignmentsGrid = document.getElementById('assignments');
        if (!assignmentsGrid) return;

        const assignments = Array.from(assignmentsGrid.children);
        const courseValue = document.getElementById('course-filter').value.toLowerCase();
        const statusValue = document.getElementById('status-filter').value.toLowerCase();
        const sortValue = document.getElementById('sort-filter').value;

        assignments.forEach(assignment => {
            const course = assignment.querySelector('.assignment-course').textContent.toLowerCase();
            const status = assignment.querySelector('.assignment-status').textContent.toLowerCase();

            const courseMatch = courseValue === '' || course.includes(courseValue);
            const statusMatch = statusValue === '' || status.includes(statusValue);

            assignment.style.display = courseMatch && statusMatch ? 'block' : 'none';
        });

        const visibleAssignments = assignments.filter(a => a.style.display !== 'none');

        visibleAssignments.sort((a, b) => {
            switch (sortValue) {
                case 'due_date_asc':
                    return new Date(a.querySelector('.assignment-due-date').textContent.split('Due: ')[1]) -
                        new Date(b.querySelector('.assignment-due-date').textContent.split('Due: ')[1]);
                case 'due_date_desc':
                    return new Date(b.querySelector('.assignment-due-date').textContent.split('Due: ')[1]) -
                        new Date(a.querySelector('.assignment-due-date').textContent.split('Due: ')[1]);
                case 'title_asc':
                    return a.querySelector('.assignment-title').textContent.localeCompare(b.querySelector('.assignment-title').textContent);
                case 'title_desc':
                    return b.querySelector('.assignment-title').textContent.localeCompare(a.querySelector('.assignment-title').textContent);
                default:
                    return 0;
            }
        });

        visibleAssignments.forEach(assignment => assignmentsGrid.appendChild(assignment));
    }

    // Settings page functionality
    function setupSettingsPage() {
        if (showGithubTokenBtn) {
            showGithubTokenBtn.addEventListener('click', function () {
                const githubTokenInput = document.getElementById('github_token');
                if (githubTokenInput.type === 'password') {
                    githubTokenInput.type = 'text';
                    this.textContent = 'Hide';
                } else {
                    githubTokenInput.type = 'password';
                    this.textContent = 'Show';
                }
            });
        }

        if (deleteAccountBtn && deleteAccountModal) {
            const confirmDeleteBtn = document.getElementById('confirm-delete');
            const cancelDeleteBtn = document.getElementById('cancel-delete');

            deleteAccountBtn.addEventListener('click', () => {
                deleteAccountModal.style.display = 'block';
            });

            cancelDeleteBtn.addEventListener('click', () => {
                deleteAccountModal.style.display = 'none';
            });

            confirmDeleteBtn.addEventListener('click', () => {
                showLoadingSpinner();
                fetch('/delete_account', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken()
                    }
                })
                    .then(response => response.json())
                    .then(data => {
                        hideLoadingSpinner();
                        if (data.success) {
                            showNotification('Account deleted successfully. Redirecting...', 'success');
                            setTimeout(() => {
                                window.location.href = '/logout';
                            }, 2000);
                        } else {
                            showNotification(data.message || 'Error deleting account. Please try again.', 'error');
                        }
                    })
                    .catch(error => {
                        hideLoadingSpinner();
                        console.error('Error:', error);
                        showNotification('An error occurred. Please try again.', 'error');
                    });
                deleteAccountModal.style.display = 'none';
            });
        }
    }

    // Populate time zone options
    function populateTimeZones() {
        if (timeZoneSelect) {
            const timeZones = moment.tz.names();
            timeZones.forEach(zone => {
                const option = document.createElement('option');
                option.value = zone;
                option.textContent = zone;
                timeZoneSelect.appendChild(option);
            });
        }
    }

    // Course details toggle
    function setupCourseDetailsToggle() {
        const courseToggleDetailsBtns = document.querySelectorAll('.course .toggle-details');
        courseToggleDetailsBtns.forEach(btn => {
            btn.addEventListener('click', function () {
                const details = this.closest('.course').querySelector('.course-details');
                if (details.style.display === 'none') {
                    details.style.display = 'block';
                    this.textContent = 'Less Details';
                } else {
                    details.style.display = 'none';
                    this.textContent = 'More Details';
                }
            });
        });
    }

    // Check authentication status
    function checkAuthStatus() {
        fetch('/check_auth_status')
            .then(response => response.json())
            .then(data => {
                if (!data.authenticated) {
                    showNotification('Your session has expired. Please log in again.', 'warning');
                    setTimeout(() => {
                        window.location.href = '/authorize';
                    }, 2000);
                }
            })
            .catch(error => {
                console.error('Error checking auth status:', error);
                showNotification('An error occurred. Please refresh the page.', 'error');
            });
    }

    // Analytics functionality
    let analyticsCharts = {};

    function initializeAnalytics() {
        console.log("Initializing analytics...");
        fetchAnalyticsData();
    }

    function fetchAnalyticsData() {
        console.log('Fetching analytics data...');
        document.getElementById('loading-message').style.display = 'block';
        document.getElementById('error-message').style.display = 'none';
        showLoadingSpinner();
        fetch('/get_analytics_data')
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                console.log('Analytics data received:', data);
                hideLoadingSpinner();
                document.getElementById('loading-message').style.display = 'none';
                if (data.error) {
                    showNotification(data.error, 'error');
                    document.getElementById('error-message').textContent = data.error;
                    document.getElementById('error-message').style.display = 'block';
                } else {
                    renderAnalytics(data);
                }
            })
            .catch(error => {
                console.error('Error fetching analytics data:', error);
                hideLoadingSpinner();
                document.getElementById('loading-message').style.display = 'none';
                document.getElementById('error-message').textContent = 'Failed to load analytics. Please try again later.';
                document.getElementById('error-message').style.display = 'block';
                showNotification('Failed to load analytics. Please try again later.', 'error');
            });
    }

    function renderAnalytics(data) {
        console.log('Rendering analytics...');
        updateOverviewSection(data);
        createCharts(data);
        updateCourseAnalyticsTable(data.course_analytics);
    }

    function updateOverviewSection(data) {
        document.getElementById('total-courses').textContent = data.total_courses;
        document.getElementById('total-assignments').textContent = data.total_assignments;
        document.getElementById('overall-completion-rate').textContent = data.overall_completion_rate.toFixed(2) + '%';
        document.getElementById('average-grade').textContent = data.average_grade.toFixed(2);
    }

    function createCharts(data) {
        createSubmissionChart(data.submission_timeline);
        createCompletionChart(data.course_analytics);
        createGradeDistributionChart(data.grade_distribution);
        createWorkloadDistributionChart(data.workload_distribution);
    }

    function createSubmissionChart(timelineData) {
        const ctx = document.getElementById('submissionChart').getContext('2d');
        analyticsCharts.submissionChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: Object.keys(timelineData),
                datasets: [{
                    label: 'Submissions',
                    data: Object.values(timelineData),
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
    }

    function createCompletionChart(courseData) {
        const ctx = document.getElementById('completionChart').getContext('2d');
        analyticsCharts.completionChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: courseData.map(course => course.course_name),
                datasets: [{
                    label: 'Completion Rate (%)',
                    data: courseData.map(course => course.completion_rate),
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
    }

    function createGradeDistributionChart(gradeData) {
        const ctx = document.getElementById('gradeDistributionChart').getContext('2d');
        analyticsCharts.gradeDistributionChart = new Chart(ctx, {
            type: 'pie',
            data: {
                labels: ['A', 'B', 'C', 'D', 'F'],
                datasets: [{
                    data: gradeData,
                    backgroundColor: [
                        'rgba(75, 192, 192, 0.6)',
                        'rgba(54, 162, 235, 0.6)',
                        'rgba(255, 206, 86, 0.6)',
                        'rgba(255, 159, 64, 0.6)',
                        'rgba(255, 99, 132, 0.6)'
                    ]
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        position: 'top',
                    }
                }
            }
        });
    }

    function createWorkloadDistributionChart(workloadData) {
        const ctx = document.getElementById('workloadDistributionChart').getContext('2d');
        analyticsCharts.workloadDistributionChart = new Chart(ctx, {
            type: 'radar',
            data: {
                labels: ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'],
                datasets: [{
                    label: 'Assignment Due Dates',
                    data: workloadData,
                    fill: true,
                    backgroundColor: 'rgba(255, 99, 132, 0.2)',
                    borderColor: 'rgb(255, 99, 132)',
                    pointBackgroundColor: 'rgb(255, 99, 132)',
                    pointBorderColor: '#fff',
                    pointHoverBackgroundColor: '#fff',
                    pointHoverBorderColor: 'rgb(255, 99, 132)'
                }]
            },
            options: {
                elements: {
                    line: {
                        borderWidth: 3
                    }
                }
            }
        });
    }

    function updateCourseAnalyticsTable(courseData) {
        const table = $('#courseDetailsTable').DataTable();
        table.clear();

        courseData.forEach(course => {
            table.row.add([
                course.course_name,
                course.total_assignments,
                course.submitted_assignments,
                course.completion_rate.toFixed(2) + '%',
                course.average_grade.toFixed(2)
            ]);
        });

        table.draw();
    }

    function setupAnalyticsPage() {
        console.log('Setting up analytics page...');

        // Show loading spinner
        document.getElementById('loading-spinner').style.display = 'block';

        // Hide error message initially
        document.getElementById('error-message').style.display = 'none';

        // Fetch analytics data
        fetch('/get_analytics_data')
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                console.log('Analytics data received:', data);

                // Hide loading spinner
                document.getElementById('loading-spinner').style.display = 'none';

                // Update overview section
                document.getElementById('total-courses').textContent = data.total_courses;
                document.getElementById('total-assignments').textContent = data.total_assignments;
                document.getElementById('overall-completion-rate').textContent = `${data.overall_completion_rate.toFixed(2)}%`;
                document.getElementById('average-grade').textContent = data.average_grade.toFixed(2);

                // Create charts
                createSubmissionChart(data.submission_timeline);
                createCompletionChart(data.course_analytics);
                createGradeDistributionChart(data.grade_distribution);
                createWorkloadDistributionChart(data.workload_distribution);

                // Update course analytics table
                updateCourseAnalyticsTable(data.course_analytics);
            })
            .catch(error => {
                console.error('Error fetching analytics data:', error);
                document.getElementById('loading-spinner').style.display = 'none';
                document.getElementById('error-message').textContent = 'Failed to load analytics. Please try again later.';
                document.getElementById('error-message').style.display = 'block';
            });
    }

    function createSubmissionChart(timelineData) {
        const ctx = document.getElementById('submissionChart').getContext('2d');
        new Chart(ctx, {
            type: 'line',
            data: {
                labels: Object.keys(timelineData),
                datasets: [{
                    label: 'Submissions',
                    data: Object.values(timelineData),
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
    }

    function createCompletionChart(courseData) {
        const ctx = document.getElementById('completionChart').getContext('2d');
        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: courseData.map(course => course.course_name),
                datasets: [{
                    label: 'Completion Rate (%)',
                    data: courseData.map(course => course.completion_rate),
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
    }

    function createGradeDistributionChart(gradeData) {
        const ctx = document.getElementById('gradeDistributionChart').getContext('2d');
        new Chart(ctx, {
            type: 'pie',
            data: {
                labels: ['A', 'B', 'C', 'D', 'F'],
                datasets: [{
                    data: gradeData,
                    backgroundColor: [
                        'rgba(75, 192, 192, 0.6)',
                        'rgba(54, 162, 235, 0.6)',
                        'rgba(255, 206, 86, 0.6)',
                        'rgba(255, 159, 64, 0.6)',
                        'rgba(255, 99, 132, 0.6)'
                    ]
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        position: 'top',
                    }
                }
            }
        });
    }

    function createWorkloadDistributionChart(workloadData) {
        const ctx = document.getElementById('workloadDistributionChart').getContext('2d');
        new Chart(ctx, {
            type: 'radar',
            data: {
                labels: ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'],
                datasets: [{
                    label: 'Assignment Due Dates',
                    data: workloadData,
                    fill: true,
                    backgroundColor: 'rgba(255, 99, 132, 0.2)',
                    borderColor: 'rgb(255, 99, 132)',
                    pointBackgroundColor: 'rgb(255, 99, 132)',
                    pointBorderColor: '#fff',
                    pointHoverBackgroundColor: '#fff',
                    pointHoverBorderColor: 'rgb(255, 99, 132)'
                }]
            },
            options: {
                elements: {
                    line: {
                        borderWidth: 3
                    }
                }
            }
        });
    }

    function updateCourseAnalyticsTable(courseData) {
        const tableBody = document.querySelector('#courseDetailsTable tbody');
        tableBody.innerHTML = ''; // Clear existing rows

        courseData.forEach(course => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${course.course_name}</td>
                <td>${course.total_assignments}</td>
                <td>${course.submitted_assignments}</td>
                <td>${course.completion_rate.toFixed(2)}%</td>
                <td>${course.average_grade.toFixed(2)}</td>
            `;
            tableBody.appendChild(row);
        });

        // If you're using DataTables, reinitialize it here
        if ($.fn.DataTable.isDataTable('#courseDetailsTable')) {
            $('#courseDetailsTable').DataTable().destroy();
        }
        $('#courseDetailsTable').DataTable({
            responsive: true,
            order: [[3, 'desc']] // Sort by completion rate descending
        });
    }

    // View Details functionality
    document.querySelectorAll('.view-details').forEach(button => {
        button.addEventListener('click', function () {
            const assignmentId = this.getAttribute('data-assignment-id');
            fetchAssignmentDetails(assignmentId);
        });
    });

    // Initialize components
    setupThemeToggle();
    applyTheme();
    if (courseFilter && statusFilter && sortFilter) {
        courseFilter.addEventListener('change', applyFiltersAndSort);
        statusFilter.addEventListener('change', applyFiltersAndSort);
        sortFilter.addEventListener('change', applyFiltersAndSort);
    }
    if (document.getElementById('analyticsContainer')) {
        setupAnalyticsPage();
    }
    document.getElementById('course-filter').addEventListener('change', applyFiltersAndSort);
    document.getElementById('status-filter').addEventListener('change', applyFiltersAndSort);
    document.getElementById('sort-filter').addEventListener('change', applyFiltersAndSort);
    setupCourseDetailsToggle();
    setInterval(checkAuthStatus, 5 * 60 * 1000); // Check auth status every 5 minutes
    initializeAnalytics();
    checkAuthStatus();
    setupAssignmentCards();
    setupSettingsPage();
    applyFiltersAndSort();
    populateTimeZones();


});
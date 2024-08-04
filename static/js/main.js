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
    const assignmentsGrid = document.getElementById('assignments-grid');
    const timeZoneSelect = document.getElementById('time_zone');
    const showGithubTokenBtn = document.getElementById('show-github-token');
    const deleteAccountBtn = document.getElementById('delete-account');
    const deleteAccountModal = document.getElementById('delete-account-modal');

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
            button.addEventListener('click', function() {
                const assignmentId = this.getAttribute('data-assignment-id');
                fetchAssignmentDetails(assignmentId);
            });
        });

        // Submit Assignment functionality
        document.querySelectorAll('.submit-form').forEach(form => {
            form.addEventListener('submit', function(e) {
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
        closeSpan.onclick = function() {
            modal.style.display = 'none';
        }
    
        window.onclick = function(event) {
            if (event.target == modal) {
                modal.style.display = 'none';
            }
        }
    
        document.addEventListener('keydown', function(event) {
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

    document.querySelectorAll('.open-assignment').forEach(button => {
        button.addEventListener('click', function() {
            const assignmentId = this.getAttribute('data-assignment-id');
            showLoadingSpinner();
            fetch(`/open_assignment/${assignmentId}`)
                .then(response => response.json())
                .then(data => {
                    hideLoadingSpinner();
                    if (data.success && data.file_url) {
                        window.open(data.file_url, '_blank');
                    } else {
                        showNotification(data.message || 'Error opening assignment. Please try again.', 'error');
                    }
                })
                .catch(error => {
                    hideLoadingSpinner();
                    console.error('Error:', error);
                    showNotification('An error occurred. Please try again.', 'error');
                });
        });
    });

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
        if (!assignmentsGrid) return;

        const assignments = Array.from(assignmentsGrid.children);
        const courseValue = courseFilter.value.toLowerCase();
        const statusValue = statusFilter.value.toLowerCase();
        const sortValue = sortFilter.value;

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
                    return a.querySelector('h2').textContent.localeCompare(b.querySelector('h2').textContent);
                case 'title_desc':
                    return b.querySelector('h2').textContent.localeCompare(a.querySelector('h2').textContent);
                default:
                    return 0;
            }
        });

        visibleAssignments.forEach(assignment => assignmentsGrid.appendChild(assignment));
    }

    // Settings page functionality
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

    function getCsrfToken() {
        const cookies = document.cookie.split(';');
        for (let cookie of cookies) {
            const [name, value] = cookie.trim().split('=');
            if (name === 'csrf_token') {
                return value;
            }
        }
        return null;
    }

    // Delete account functionality
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
                    'X-CSRFToken': getCsrfToken() // Implement this function to get the CSRF token
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

    // Populate time zone options
    if (timeZoneSelect) {
        const timeZones = moment.tz.names();
        timeZones.forEach(zone => {
            const option = document.createElement('option');
            option.value = zone;
            option.textContent = zone;
            timeZoneSelect.appendChild(option);
        });
    }

    // Course details toggle
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

    // Check authentication status
    function checkAuthStatus() {
        fetch('/check_auth_status')
            .then(response => response.json())
            .then(data => {
                if (!data.authenticated) {
                    window.location.href = '/authorize';
                }
            })
            .catch(error => console.error('Error checking auth status:', error));
    }

    // Initialize components
    setupThemeToggle();
    applyTheme();
    if (courseFilter && statusFilter && sortFilter) {
        courseFilter.addEventListener('change', applyFiltersAndSort);
        statusFilter.addEventListener('change', applyFiltersAndSort);
        sortFilter.addEventListener('change', applyFiltersAndSort);
        applyFiltersAndSort();
    }
    setInterval(checkAuthStatus, 5 * 60 * 1000); // Check auth status every 5 minutes
    checkAuthStatus();
});
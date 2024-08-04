document.addEventListener('DOMContentLoaded', function () {
    const assignmentCards = document.querySelectorAll('.assignment');
    const fileInputs = document.querySelectorAll('.file-input');
    const submitButtons = document.querySelectorAll('.submit-btn');
    const themeToggle = document.getElementById('theme-toggle');
    const loadingSpinner = document.getElementById('loading');
    const courseFilter = document.getElementById('course-filter');
    const statusFilter = document.getElementById('status-filter');
    const sortFilter = document.getElementById('sort-filter');
    const assignmentsGrid = document.getElementById('assignments-grid');

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
                // Save the theme preference
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

    function showLoadingSpinner() {
        document.getElementById('loading').style.display = 'flex';
    }

    function hideLoadingSpinner() {
        document.getElementById('loading').style.display = 'none';
    }

    // Assignment card hover effect
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

    // File input change event
    fileInputs.forEach(input => {
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

    // Submit button click event
    submitButtons.forEach(button => {
        button.addEventListener('click', function () {
            const assignmentId = this.dataset.assignmentId;
            const fileInput = document.getElementById(`file-${assignmentId}`);

            if (!fileInput || fileInput.files.length === 0) {
                showNotification('Please select a file to upload.', 'error');
                return;
            }

            const formData = new FormData();
            formData.append('file', fileInput.files[0]);

            if (loadingSpinner) {
                loadingSpinner.style.display = 'block';
            }
            showLoadingSpinner();

            fetch(`/submit/${assignmentId}`, {
                method: 'POST',
                body: formData
            })
                .then(response => response.json())
                .then(data => {
                    hideLoadingSpinner();
                    if (data.success) {
                        showNotification('Assignment submitted successfully!', 'success');
                        updateAssignmentStatus(assignmentId, 'Submitted');
                    } else {
                        showNotification(data.message || 'Error submitting assignment. Please try again.', 'error');
                    }
                })
                .catch(error => {
                    hideLoadingSpinner();
                    console.error('Error:', error);
                    showNotification('An error occurred. Please try again.', 'error');
                });
        });
    });

    document.querySelectorAll('.view-details').forEach(button => {
        button.addEventListener('click', function() {
            const assignmentId = this.getAttribute('data-assignment-id');
            fetchAssignmentDetails(assignmentId);
        });
    });

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

    function displayAssignmentDetails(assignment) {
        // Create modal container if it doesn't exist
        let modal = document.getElementById('assignment-details-modal');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'assignment-details-modal';
            modal.className = 'modal';
            document.body.appendChild(modal);
        }
    
        // Create modal content
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
    
        // Set modal content
        modal.innerHTML = detailsHtml;
    
        // Display modal
        modal.style.display = 'block';
    
        // Close modal when clicking on <span> (x)
        const closeSpan = modal.querySelector('.close');
        closeSpan.onclick = function() {
            modal.style.display = 'none';
        }
    
        // Close modal when clicking outside of it
        window.onclick = function(event) {
            if (event.target == modal) {
                modal.style.display = 'none';
            }
        }
    
        // Add escape key listener to close modal
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

    function updateAssignmentStatus(assignmentId, status, grade = null) {
        const assignmentCard = document.querySelector(`.assignment[data-id="${assignmentId}"]`);
        if (assignmentCard) {
            const statusElement = assignmentCard.querySelector('.assignment-status');
            const submitButton = assignmentCard.querySelector('.submit-btn');
            const fileUpload = assignmentCard.querySelector('.file-upload');

            if (grade !== null) {
                status = 'Graded';
                const gradeElement = assignmentCard.querySelector('.assignment-grade');
                if (gradeElement) {
                    gradeElement.textContent = `Grade: ${grade}`;
                } else {
                    const newGradeElement = document.createElement('p');
                    newGradeElement.className = 'assignment-grade';
                    newGradeElement.innerHTML = `<i class="fas fa-star"></i> Grade: ${grade}`;
                    assignmentCard.insertBefore(newGradeElement, submitButton || fileUpload);
                }
            }

            statusElement.innerHTML = `<i class="fas fa-circle"></i> ${status}`;
            statusElement.className = `assignment-status status-${status.toLowerCase().replace(' ', '-')}`;

            if (status === 'Submitted' || status === 'Graded') {
                if (submitButton) submitButton.style.display = 'none';
                if (fileUpload) fileUpload.style.display = 'none';
            }
        }
    }

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

    // Toggle assignment details
    const toggleDetailsBtns = document.querySelectorAll('.toggle-details');
    toggleDetailsBtns.forEach(btn => {
        btn.addEventListener('click', function () {
            const details = this.nextElementSibling;
            if (details.style.display === 'none') {
                details.style.display = 'block';
                this.textContent = 'Hide Details';
            } else {
                details.style.display = 'none';
                this.textContent = 'Show Details';
            }
        });
    });

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


    // Settings page: Show/Hide GitHub token
    const showGithubTokenBtn = document.getElementById('show-github-token');
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

    // Delete account functionality
    const deleteAccountBtn = document.getElementById('delete-account');
    const deleteAccountModal = document.getElementById('delete-account-modal');
    const confirmDeleteBtn = document.getElementById('confirm-delete');
    const cancelDeleteBtn = document.getElementById('cancel-delete');

    if (deleteAccountBtn && deleteAccountModal) {
        deleteAccountBtn.addEventListener('click', () => {
            deleteAccountModal.style.display = 'block';
        });

        cancelDeleteBtn.addEventListener('click', () => {
            deleteAccountModal.style.display = 'none';
        });

        confirmDeleteBtn.addEventListener('click', () => {
            // Add your account deletion logic here
            console.log('Account deletion confirmed');
            deleteAccountModal.style.display = 'none';
        });
    }

    function applyFiltersAndSort() {
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

    courseFilter.addEventListener('change', applyFiltersAndSort);
    statusFilter.addEventListener('change', applyFiltersAndSort);
    sortFilter.addEventListener('change', applyFiltersAndSort);

    // Initialize components
    applyFiltersAndSort();
    setupThemeToggle();
    applyTheme();
    setInterval(checkAuthStatus, 5 * 60 * 1000);
    checkAuthStatus();

    // Populate time zone options
    const timeZoneSelect = document.getElementById('time_zone');
    if (timeZoneSelect) {
        const timeZones = moment.tz.names();
        timeZones.forEach(zone => {
            const option = document.createElement('option');
            option.value = zone;
            option.textContent = zone;
            timeZoneSelect.appendChild(option);
        });
    }
});
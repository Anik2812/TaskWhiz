document.addEventListener('DOMContentLoaded', function () {
    const searchInput = document.getElementById('search-input');
    const courseFilter = document.getElementById('course-filter');
    const statusFilter = document.getElementById('status-filter');
    const sortFilter = document.getElementById('sort-filter');
    const assignmentsGrid = document.getElementById('assignments');

    // Function to filter and sort assignments
    function filterAndSortAssignments() {
        const searchTerm = searchInput.value.toLowerCase();
        const selectedCourse = courseFilter.value.toLowerCase();
        const selectedStatus = statusFilter.value.toLowerCase();
        const sortOption = sortFilter.value;

        const assignments = Array.from(assignmentsGrid.children);

        assignments.forEach(assignment => {
            const title = assignment.querySelector('.assignment-title').textContent.toLowerCase();
            const course = assignment.querySelector('.assignment-course').textContent.toLowerCase();
            const status = assignment.querySelector('.assignment-status').textContent.toLowerCase();

            const matchesSearch = title.includes(searchTerm);
            const matchesCourse = selectedCourse === '' || course.includes(selectedCourse);
            const matchesStatus = selectedStatus === '' || status.includes(selectedStatus);

            assignment.style.display = matchesSearch && matchesCourse && matchesStatus ? 'block' : 'none';
        });

        // Sort visible assignments
        const visibleAssignments = assignments.filter(a => a.style.display !== 'none');
        visibleAssignments.sort((a, b) => {
            const aValue = getSortValue(a, sortOption);
            const bValue = getSortValue(b, sortOption);
            return sortOption.includes('desc') ? bValue.localeCompare(aValue) : aValue.localeCompare(bValue);
        });

        visibleAssignments.forEach(assignment => assignmentsGrid.appendChild(assignment));
    }

    function getSortValue(assignment, sortOption) {
        switch (sortOption) {
            case 'due_date_asc':
            case 'due_date_desc':
                return assignment.querySelector('.assignment-due-date').textContent;
            case 'title_asc':
            case 'title_desc':
                return assignment.querySelector('.assignment-title').textContent;
            default:
                return '';
        }
    }

    // Add event listeners
    searchInput.addEventListener('input', filterAndSortAssignments);
    courseFilter.addEventListener('change', filterAndSortAssignments);
    statusFilter.addEventListener('change', filterAndSortAssignments);
    sortFilter.addEventListener('change', filterAndSortAssignments);

    // View Details functionality
    assignmentsGrid.addEventListener('click', function (e) {
        if (e.target.classList.contains('view-details')) {
            const assignmentId = e.target.getAttribute('data-assignment-id');
            fetchAssignmentDetails(assignmentId);
        }
    });

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
            <p><strong>Description:</strong> ${assignment.description || 'No description available'}</p>
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

    function submitAssignment(assignmentId, file) {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('assignment_id', assignmentId);

        fetch('/submit_assignment', {
            method: 'POST',
            body: formData
        })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    showNotification('Assignment submitted successfully!', 'success');
                    updateAssignmentStatus(assignmentId, 'Submitted');
                } else {
                    showNotification(data.message || 'Error submitting assignment.', 'error');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showNotification('An error occurred while submitting the assignment.', 'error');
            });
    }

    function updateAssignmentStatus(assignmentId, newStatus) {
        const assignmentCard = document.querySelector(`.assignment-card[data-assignment-id="${assignmentId}"]`);
        if (assignmentCard) {
            const statusElement = assignmentCard.querySelector('.assignment-status');
            statusElement.innerHTML = `<i class="fas fa-circle"></i> ${newStatus}`;
            statusElement.className = `assignment-status status-${newStatus.toLowerCase().replace(' ', '-')}`;

            const cardActions = assignmentCard.querySelector('.card-actions');
            cardActions.innerHTML = `
                <button class="btn btn-secondary open-assignment" data-assignment-id="${assignmentId}">
                    <i class="fas fa-folder-open"></i> Open
                </button>
            `;
        }
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

            // View Details functionality
            card.querySelector('.toggle-details').addEventListener('click', function () {
                const assignmentId = this.closest('.assignment-card').dataset.assignmentId;
                fetchAssignmentDetails(assignmentId);
            });
        });

        // Submit Assignment functionality
        document.querySelectorAll('.submit-form').forEach(form => {
            form.addEventListener('submit', function (e) {
                e.preventDefault();
                const assignmentId = this.querySelector('.submit-btn').dataset.assignmentId;
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

    function showNotification(message, type) {
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.textContent = message;
        document.body.appendChild(notification);

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

    // Initial filter and sort
    filterAndSortAssignments();
});
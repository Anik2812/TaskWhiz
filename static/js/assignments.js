document.addEventListener('DOMContentLoaded', function() {
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
    assignmentsGrid.addEventListener('click', function(e) {
        if (e.target.classList.contains('view-details')) {
            const assignmentId = e.target.getAttribute('data-assignment-id');
            fetchAssignmentDetails(assignmentId);
        }
    });

    function fetchAssignmentDetails(assignmentId) {
        fetch(`/assignment/${assignmentId}`)
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    displayAssignmentDetails(data.assignment);
                } else {
                    showNotification(data.message || 'Error fetching assignment details.', 'error');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showNotification('An error occurred while fetching assignment details.', 'error');
            });
    }

    function displayAssignmentDetails(assignment) {
        const modal = document.createElement('div');
        modal.className = 'modal';
        modal.innerHTML = `
            <div class="modal-content">
                <span class="close">&times;</span>
                <h2>${assignment.title}</h2>
                <p><strong>Course:</strong> ${assignment.course}</p>
                <p><strong>Due Date:</strong> ${assignment.due_date}</p>
                <p><strong>Status:</strong> ${assignment.status}</p>
                <p><strong>Description:</strong> ${assignment.description}</p>
                ${assignment.grade ? `<p><strong>Grade:</strong> ${assignment.grade} / ${assignment.total_marks}</p>` : ''}
            </div>
        `;
        document.body.appendChild(modal);

        const closeBtn = modal.querySelector('.close');
        closeBtn.onclick = function() {
            modal.remove();
        }

        window.onclick = function(event) {
            if (event.target == modal) {
                modal.remove();
            }
        }
    }

    // File upload functionality
    assignmentsGrid.addEventListener('change', function(e) {
        if (e.target.classList.contains('file-input')) {
            const fileName = e.target.files[0].name;
            const label = e.target.nextElementSibling;
            label.innerHTML = `<i class="fas fa-file"></i> ${fileName}`;
        }
    });

    // Submit assignment functionality
    assignmentsGrid.addEventListener('click', function(e) {
        if (e.target.classList.contains('submit-btn')) {
            const assignmentId = e.target.getAttribute('data-assignment-id');
            const fileInput = document.getElementById(`file-${assignmentId}`);
            if (fileInput.files.length === 0) {
                showNotification('Please select a file to upload.', 'error');
                return;
            }
            submitAssignment(assignmentId, fileInput.files[0]);
        }
    });

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
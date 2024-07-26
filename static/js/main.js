document.addEventListener('DOMContentLoaded', function() {
    const assignmentCards = document.querySelectorAll('.assignment');
    const fileInputs = document.querySelectorAll('.file-input');
    const submitButtons = document.querySelectorAll('.submit-btn');
    const themeToggle = document.getElementById('theme-toggle');
    const loadingSpinner = document.getElementById('loading');

    // Theme toggle functionality
    themeToggle.addEventListener('click', function(e) {
        e.preventDefault();
        document.body.classList.toggle('dark-theme');
        const icon = this.querySelector('i');
        if (icon.classList.contains('fa-moon')) {
            icon.classList.replace('fa-moon', 'fa-sun');
        } else {
            icon.classList.replace('fa-sun', 'fa-moon');
        }
    });

    // Assignment card hover effect
    assignmentCards.forEach(card => {
        card.addEventListener('mouseenter', function() {
            this.style.transform = 'scale(1.03)';
        });
        card.addEventListener('mouseleave', function() {
            this.style.transform = 'scale(1)';
        });
    });

    // File input change event
    fileInputs.forEach(input => {
        input.addEventListener('change', function(e) {
            const fileName = e.target.files[0].name;
            const assignmentId = this.dataset.assignmentId;
            const label = document.querySelector(`label[for="file-${assignmentId}"]`);
            label.innerHTML = `<i class="fas fa-file"></i> ${fileName}`;
        });
    });

    // Submit button click event
    submitButtons.forEach(button => {
        button.addEventListener('click', function() {
            const assignmentId = this.dataset.assignmentId;
            const fileInput = document.getElementById(`file-${assignmentId}`);
            
            if (fileInput.files.length === 0) {
                alert('Please select a file to upload.');
                return;
            }

            const formData = new FormData();
            formData.append('file', fileInput.files[0]);

            loadingSpinner.style.display = 'block';

            fetch(`/submit/${assignmentId}`, {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                loadingSpinner.style.display = 'none';
                if (data.success) {
                    alert('Assignment submitted successfully!');
                    updateAssignmentStatus(assignmentId, 'Completed');
                } else {
                    alert('Error submitting assignment. Please try again.');
                }
            })
            .catch(error => {
                loadingSpinner.style.display = 'none';
                console.error('Error:', error);
                alert('An error occurred. Please try again.');
            });
        });
    });

    function updateAssignmentStatus(assignmentId, status) {
        const statusElement = document.querySelector(`.assignment[data-id="${assignmentId}"] .assignment-status`);
        statusElement.textContent = status;
        statusElement.className = `assignment-status status-${status.toLowerCase()}`;
    }

    // Add smooth scrolling to all links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            document.querySelector(this.getAttribute('href')).scrollIntoView({
                behavior: 'smooth'
            });
        });
    });
});
document.addEventListener('DOMContentLoaded', function() {
    const assignmentCards = document.querySelectorAll('.assignment');

    assignmentCards.forEach(card => {
        card.addEventListener('click', function() {
            this.classList.toggle('expanded');
        });
    });

    const submissionForms = document.querySelectorAll('form');
    submissionForms.forEach(form => {
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            const formData = new FormData(this);
            fetch(this.action, {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('Assignment submitted successfully!');
                } else {
                    alert('Error submitting assignment. Please try again.');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('An error occurred. Please try again.');
            });
        });
    });
});
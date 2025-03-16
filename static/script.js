document.addEventListener("DOMContentLoaded", function() {
    // Add a subtle fade-in effect to the main content
    const mainContent = document.querySelector('main');
    mainContent.style.opacity = 0;
    mainContent.style.transition = 'opacity 0.5s ease';
    setTimeout(() => {
        mainContent.style.opacity = 1;
    }, 100);

    // Add a hover effect to the header buttons
    const headerButtons = document.querySelectorAll('header nav a');
    headerButtons.forEach(button => {
        button.addEventListener('mouseenter', () => {
            button.style.transform = 'scale(1.05)';
        });
        button.addEventListener('mouseleave', () => {
            button.style.transform = 'scale(1)';
        });
    });
});
document.addEventListener('DOMContentLoaded', () => {
    const header = document.querySelector('.app-header');
    const darkModeSwitch = document.querySelector('.dark-mode-switch input');
    const flashMessages = document.querySelectorAll('.flash');
    // NEW: Get hamburger elements
    const hamburger = document.querySelector('.hamburger');
    const navMenu = document.querySelector('.nav-menu');

    // 1. Sticky Header Effect
    if (header) {
        window.addEventListener('scroll', () => {
            if (window.scrollY > 10) {
                header.classList.add('scrolled');
            } else {
                header.classList.remove('scrolled');
            }
        });
    }

    // 2. Dark Mode Toggle & Persistence
    if (darkModeSwitch) {
        const currentTheme = localStorage.getItem('theme');
        if (currentTheme === 'dark') {
            document.body.classList.add('dark-mode');
            darkModeSwitch.checked = true;
        }
        darkModeSwitch.addEventListener('change', () => {
            document.body.classList.toggle('dark-mode');
            let theme = document.body.classList.contains('dark-mode') ? 'dark' : 'light';
            localStorage.setItem('theme', theme);
        });
    }

    // 3. Auto-hide Flash Messages
    if (flashMessages.length > 0) {
        flashMessages.forEach(function(message) {
            setTimeout(() => {
                message.style.transition = 'opacity 0.5s ease';
                message.style.opacity = '0';
                setTimeout(() => { message.style.display = 'none'; }, 500);
            }, 5000);
        });
    }

    // 4. NEW: Hamburger Menu Toggle Logic
    if (hamburger && navMenu) {
        hamburger.addEventListener('click', () => {
            hamburger.classList.toggle('active');
            navMenu.classList.toggle('active');
        });
    }
});

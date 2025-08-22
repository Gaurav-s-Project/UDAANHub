document.addEventListener('DOMContentLoaded', () => {
    const header = document.querySelector('.app-header');
    const hamburger = document.querySelector('.hamburger');
    const navMenu = document.querySelector('.nav-menu');
    const darkModeSwitch = document.querySelector('.dark-mode-switch input');
    const flashMessages = document.querySelectorAll('.flash');
    const cards = document.querySelectorAll('.card');
    const editModal = document.getElementById('edit-modal');
    const editDetailsBtn = document.getElementById('edit-details-btn');
    const closeModalBtn = document.querySelector('.close-modal');
    const queueSearchInput = document.getElementById('queue-search');

    const studentListSearch = document.getElementById('student-list-search');
    if (studentListSearch) {
        const studentRows = document.querySelectorAll('.student-row');
        studentListSearch.addEventListener('input', (e) => {
            const searchTerm = e.target.value.toLowerCase();
            studentRows.forEach(row => {
                const rowText = row.textContent.toLowerCase();
                row.style.display = rowText.includes(searchTerm) ? '' : 'none';
            });
        });
    }

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

    // 2. Hamburger Menu Toggle
    if (hamburger && navMenu) {
        hamburger.addEventListener('click', () => {
            hamburger.classList.toggle('active');
            navMenu.classList.toggle('active');
        });
    }

    // 3. Dark Mode Toggle & Persistence
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

    // 4. Auto-hide Flash Messages
    if (flashMessages.length > 0) {
        flashMessages.forEach(function(message) {
            setTimeout(() => {
                message.style.transition = 'opacity 0.5s ease';
                message.style.opacity = '0';
                setTimeout(() => { message.style.display = 'none'; }, 500);
            }, 5000);
        });
    }

    // 5. Scroll-based Animations for Cards
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('visible');
                observer.unobserve(entry.target);
            }
        });
    }, {
        threshold: 0.1
    });

    cards.forEach(card => {
        observer.observe(card);
    });

    // 6. Edit Details Modal Logic
    if (editDetailsBtn && editModal) {
        editDetailsBtn.addEventListener('click', () => {
            editModal.style.display = 'flex';
            setTimeout(() => {
                editModal.classList.add('visible');
            }, 10);
        });

        if (closeModalBtn) {
            closeModalBtn.addEventListener('click', () => {
                editModal.classList.remove('visible');
                setTimeout(() => {
                    editModal.style.display = 'none';
                }, 300);
            });
        }

        editModal.addEventListener('click', (e) => {
            if (e.target === editModal) {
                editModal.classList.remove('visible');
                setTimeout(() => {
                    editModal.style.display = 'none';
                }, 300);
            }
        });
    }

    // 7. Live Search for LHC Queue
    if (queueSearchInput) {
        const queueItems = document.querySelectorAll('.queue-item');
        const noResultsMessage = document.getElementById('no-results-message');

        queueSearchInput.addEventListener('input', (e) => {
            const searchTerm = e.target.value.toLowerCase();
            let visibleCount = 0;

            queueItems.forEach(item => {
                const itemText = item.textContent.toLowerCase();
                if (itemText.includes(searchTerm)) {
                    item.style.display = 'flex';
                    visibleCount++;
                } else {
                    item.style.display = 'none';
                }
            });

            if (noResultsMessage) {
                noResultsMessage.style.display = visibleCount === 0 ? 'block' : 'none';
            }
        });
    }
});

// ADD this new logic to script.js

// --- Document Verification Modal Logic ---
const docModal = document.getElementById('doc-modal');
const verifyDocsBtn = document.getElementById('verify-docs-btn');
const closeDocModalBtn = docModal ? docModal.querySelector('.close-modal') : null;

if (verifyDocsBtn && docModal) {
    verifyDocsBtn.addEventListener('click', () => {
        docModal.style.display = 'flex';
        setTimeout(() => { docModal.classList.add('visible'); }, 10);
    });

    if (closeDocModalBtn) {
        closeDocModalBtn.addEventListener('click', () => {
            docModal.classList.remove('visible');
            setTimeout(() => { docModal.style.display = 'none'; }, 300);
        });
    }

    docModal.addEventListener('click', (e) => {
        if (e.target === docModal) {
            docModal.classList.remove('visible');
            setTimeout(() => { docModal.style.display = 'none'; }, 300);
        }
    });
}

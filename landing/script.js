/**
 * Attendrix Landing Page JavaScript
 * Interactive features and animations
 */

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Initialize AOS
    if (typeof AOS !== 'undefined') {
        AOS.init({
            duration: 800,
            once: false,
            mirror: false,
            easing: 'ease-in-out'
        });
    }
    
    // Initialize all features
    initializeSmoothScrolling();
    initializeNavigation();
    initializeContactForm();
    initializeModal();
    initializeBackToTop();
    initializeAnimations();
    initializeStatistics();
    initializeLazyLoading();
    initializeTheme();
});

/**
 * Smooth scrolling for navigation links
 */
function initializeSmoothScrolling() {
    const links = document.querySelectorAll('a[href^="#"]');
    
    links.forEach(link => {
        link.addEventListener('click', function(e) {
            const targetId = this.getAttribute('href');
            
            if (targetId === '#') {
                e.preventDefault();
                return;
            }
            
            const target = document.querySelector(targetId);
            
            if (target) {
                e.preventDefault();
                
                const headerOffset = 80;
                const elementPosition = target.getBoundingClientRect().top;
                const offsetPosition = elementPosition + window.pageYOffset - headerOffset;
                
                window.scrollTo({
                    top: offsetPosition,
                    behavior: 'smooth'
                });
                
                // Update active nav link
                updateActiveNavLink(targetId);
            }
        });
    });
}

/**
 * Update active navigation link based on scroll position
 */
function updateActiveNavLink(targetId) {
    const navLinks = document.querySelectorAll('.navbar-nav .nav-link');
    
    navLinks.forEach(link => {
        link.classList.remove('active');
        if (link.getAttribute('href') === targetId) {
            link.classList.add('active');
        }
    });
}

/**
 * Navigation scroll effects
 */
function initializeNavigation() {
    const navbar = document.querySelector('.navbar');
    const navLinks = document.querySelectorAll('.navbar-nav .nav-link');
    
    // Add scroll effect to navbar
    window.addEventListener('scroll', function() {
        if (window.scrollY > 50) {
            navbar.classList.add('scrolled');
        } else {
            navbar.classList.remove('scrolled');
        }
        
        // Update active nav link based on scroll position
        updateActiveNavOnScroll();
    });
    
    // Mobile menu toggle
    const navbarToggler = document.querySelector('.navbar-toggler');
    const navbarCollapse = document.querySelector('.navbar-collapse');
    
    if (navbarToggler && navbarCollapse) {
        navbarToggler.addEventListener('click', function() {
            navbarCollapse.classList.toggle('show');
        });
        
        // Close mobile menu when clicking on a link
        navLinks.forEach(link => {
            link.addEventListener('click', function() {
                if (window.innerWidth < 992) {
                    navbarCollapse.classList.remove('show');
                }
            });
        });
    }
}

/**
 * Update active navigation link based on scroll position
 */
function updateActiveNavOnScroll() {
    const sections = document.querySelectorAll('section[id]');
    const navLinks = document.querySelectorAll('.navbar-nav .nav-link');
    
    let current = '';
    
    sections.forEach(section => {
        const sectionTop = section.offsetTop;
        const sectionHeight = section.clientHeight;
        
        if (window.scrollY >= (sectionTop - 100)) {
            current = section.getAttribute('id');
        }
    });
    
    navLinks.forEach(link => {
        link.classList.remove('active');
        if (link.getAttribute('href') === '#' + current) {
            link.classList.add('active');
        }
    });
}

/**
 * Contact form handling
 */
function initializeContactForm() {
    const contactForm = document.getElementById('contactForm');
    const successMessage = document.createElement('div');
    successMessage.className = 'alert alert-success mt-3';
    successMessage.style.display = 'none';
    successMessage.textContent = 'Thank you for your message! We\'ll get back to you within 24 hours.';
    
    if (contactForm) {
        contactForm.appendChild(successMessage);
        
        contactForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            // Get form data
            const formData = new FormData(contactForm);
            const data = {};
            
            for (let [key, value] of formData.entries()) {
                data[key] = value;
            }
            
            // Validate form
            if (!validateContactForm(data)) {
                return;
            }
            
            // Show loading state
            const submitButton = contactForm.querySelector('button[type="submit"]');
            const originalText = submitButton.textContent;
            submitButton.textContent = 'Sending...';
            submitButton.disabled = true;
            
            // Simulate form submission (replace with actual API call)
            setTimeout(() => {
                // Show success message
                successMessage.style.display = 'block';
                
                // Reset form
                contactForm.reset();
                
                // Reset button
                submitButton.textContent = originalText;
                submitButton.disabled = false;
                
                // Hide success message after 5 seconds
                setTimeout(() => {
                    successMessage.style.display = 'none';
                }, 5000);
                
                // Log submission (replace with actual analytics)
                console.log('Contact form submitted:', data);
            }, 1500);
        });
    }
}

/**
 * Validate contact form
 */
function validateContactForm(data) {
    const errors = [];
    
    if (!data.name || data.name.trim().length < 2) {
        errors.push('Please enter a valid name');
    }
    
    if (!data.email || !isValidEmail(data.email)) {
        errors.push('Please enter a valid email address');
    }
    
    if (!data.institution || data.institution.trim().length < 2) {
        errors.push('Please enter your institution name');
    }
    
    if (!data.message || data.message.trim().length < 10) {
        errors.push('Please enter a message with at least 10 characters');
    }
    
    if (errors.length > 0) {
        showFormErrors(errors);
        return false;
    }
    
    return true;
}

/**
 * Show form errors
 */
function showFormErrors(errors) {
    // Remove existing error messages
    const existingErrors = document.querySelectorAll('.alert-danger');
    existingErrors.forEach(error => error.remove());
    
    // Create error message
    const errorDiv = document.createElement('div');
    errorDiv.className = 'alert alert-danger mt-3';
    errorDiv.innerHTML = '<strong>Please fix the following errors:</strong><ul>' + 
        errors.map(error => `<li>${error}</li>`).join('') + '</ul>';
    
    const contactForm = document.getElementById('contactForm');
    contactForm.appendChild(errorDiv);
    
    // Remove error message after 5 seconds
    setTimeout(() => {
        errorDiv.remove();
    }, 5000);
}

/**
 * Validate email address
 */
function isValidEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
}

/**
 * Modal handling
 */
function initializeModal() {
    const demoModal = document.getElementById('demoModal');
    const demoButtons = document.querySelectorAll('[data-bs-target="#demoModal"], .btn:contains("Watch Demo")');
    
    demoButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            if (demoModal) {
                demoModal.classList.add('show');
                demoModal.style.display = 'block';
                document.body.classList.add('modal-open');
            }
        });
    });
    
    // Close modal
    const closeButtons = document.querySelectorAll('.modal .btn-close, .modal .btn-secondary');
    closeButtons.forEach(button => {
        button.addEventListener('click', function() {
            closeModal();
        });
    });
    
    // Close modal on backdrop click
    if (demoModal) {
        demoModal.addEventListener('click', function(e) {
            if (e.target === demoModal) {
                closeModal();
            }
        });
    }
    
    // Close modal on ESC key
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && demoModal && demoModal.classList.contains('show')) {
            closeModal();
        }
    });
}

/**
 * Close modal
 */
function closeModal() {
    const demoModal = document.getElementById('demoModal');
    if (demoModal) {
        demoModal.classList.remove('show');
        demoModal.style.display = 'none';
        document.body.classList.remove('modal-open');
    }
}

/**
 * Back to top button
 */
function initializeBackToTop() {
    const backToTopButton = document.querySelector('.back-to-top');
    
    if (backToTopButton) {
        // Show/hide button based on scroll position
        window.addEventListener('scroll', function() {
            if (window.scrollY > 300) {
                backToTopButton.style.opacity = '1';
                backToTopButton.style.visibility = 'visible';
            } else {
                backToTopButton.style.opacity = '0';
                backToTopButton.style.visibility = 'hidden';
            }
        });
        
        // Scroll to top when clicked
        backToTopButton.addEventListener('click', function(e) {
            e.preventDefault();
            window.scrollTo({
                top: 0,
                behavior: 'smooth'
            });
        });
    }
}

/**
 * Initialize animations
 */
function initializeAnimations() {
    // Animate elements on scroll
    const animatedElements = document.querySelectorAll('[data-aos]');
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('aos-animate');
            }
        });
    }, {
        threshold: 0.1
    });
    
    animatedElements.forEach(element => {
        observer.observe(element);
    });
    
    // Parallax effect for hero section
    const heroSection = document.querySelector('.hero-section');
    if (heroSection) {
        window.addEventListener('scroll', function() {
            const scrolled = window.scrollY;
            const parallax = scrolled * 0.5;
            heroSection.style.transform = `translateY(${parallax}px)`;
        });
    }
}

/**
 * Initialize statistics counters
 */
function initializeStatistics() {
    const statNumbers = document.querySelectorAll('.stat-number');
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting && !entry.target.classList.contains('counted')) {
                entry.target.classList.add('counted');
                animateCounter(entry.target);
            }
        });
    }, {
        threshold: 0.5
    });
    
    statNumbers.forEach(stat => {
        observer.observe(stat);
    });
}

/**
 * Animate counter
 */
function animateCounter(element) {
    const target = parseInt(element.textContent.replace(/[^0-9]/g, ''));
    const duration = 2000;
    const step = target / (duration / 16);
    let current = 0;
    
    const timer = setInterval(() => {
        current += step;
        if (current >= target) {
            current = target;
            clearInterval(timer);
        }
        
        // Format the number with suffix
        let displayValue = Math.floor(current);
        const suffix = element.textContent.replace(/[0-9]/g, '').trim();
        element.textContent = displayValue + suffix;
    }, 16);
}

/**
 * Initialize lazy loading for images
 */
function initializeLazyLoading() {
    const images = document.querySelectorAll('img[data-src]');
    
    const imageObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const img = entry.target;
                img.src = img.dataset.src;
                img.classList.remove('lazy');
                imageObserver.unobserve(img);
            }
        });
    });
    
    images.forEach(img => {
        img.classList.add('lazy');
        imageObserver.observe(img);
    });
}

/**
 * Initialize theme (light/dark mode)
 */
function initializeTheme() {
    const themeToggle = document.querySelector('.theme-toggle');
    const body = document.body;
    
    // Check for saved theme preference
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme) {
        body.classList.toggle('dark-theme', savedTheme === 'dark');
    }
    
    if (themeToggle) {
        themeToggle.addEventListener('click', function() {
            body.classList.toggle('dark-theme');
            const currentTheme = body.classList.contains('dark-theme') ? 'dark' : 'light';
            localStorage.setItem('theme', currentTheme);
        });
    }
}

/**
 * Performance monitoring
 */
function initializePerformanceMonitoring() {
    // Monitor page load performance
    window.addEventListener('load', function() {
        if ('performance' in window) {
            const perfData = performance.getEntriesByType('navigation')[0];
            const loadTime = perfData.loadEventEnd - perfData.loadEventStart;
            
            // Log performance data (replace with actual analytics)
            console.log('Page load time:', loadTime + 'ms');
        }
    });
    
    // Monitor Core Web Vitals
    if ('PerformanceObserver' in window) {
        // Largest Contentful Paint
        const lcpObserver = new PerformanceObserver((list) => {
            const entries = list.getEntries();
            const lastEntry = entries[entries.length - 1];
            console.log('LCP:', lastEntry.startTime);
        });
        lcpObserver.observe({ entryTypes: ['largest-contentful-paint'] });
        
        // First Input Delay
        const fidObserver = new PerformanceObserver((list) => {
            const entries = list.getEntries();
            entries.forEach(entry => {
                console.log('FID:', entry.processingStart - entry.startTime);
            });
        });
        fidObserver.observe({ entryTypes: ['first-input'] });
        
        // Cumulative Layout Shift
        let clsScore = 0;
        const clsObserver = new PerformanceObserver((list) => {
            list.getEntries().forEach(entry => {
                if (!entry.hadRecentInput) {
                    clsScore += entry.value;
                }
            });
            console.log('CLS:', clsScore);
        });
        clsObserver.observe({ entryTypes: ['layout-shift'] });
    }
}

/**
 * Initialize analytics tracking
 */
function initializeAnalytics() {
    // Track page view
    trackEvent('page_view', {
        page: window.location.pathname,
        title: document.title
    });
    
    // Track button clicks
    const trackingButtons = document.querySelectorAll('[data-track]');
    trackingButtons.forEach(button => {
        button.addEventListener('click', function() {
            const eventName = this.dataset.track;
            const eventParams = JSON.parse(this.dataset.params || '{}');
            trackEvent(eventName, eventParams);
        });
    });
    
    // Track form submissions
    const contactForm = document.getElementById('contactForm');
    if (contactForm) {
        contactForm.addEventListener('submit', function() {
            trackEvent('form_submit', {
                form: 'contact',
                source: 'landing_page'
            });
        });
    }
}

/**
 * Track analytics event
 */
function trackEvent(eventName, params) {
    // Replace with actual analytics implementation
    console.log('Analytics Event:', eventName, params);
    
    // Example: Google Analytics
    if (typeof gtag !== 'undefined') {
        gtag('event', eventName, params);
    }
}

/**
 * Initialize error handling
 */
function initializeErrorHandling() {
    window.addEventListener('error', function(e) {
        console.error('JavaScript error:', e.error);
        // Track errors (replace with actual error tracking)
        trackEvent('javascript_error', {
            message: e.message,
            filename: e.filename,
            lineno: e.lineno,
            colno: e.colno
        });
    });
    
    window.addEventListener('unhandledrejection', function(e) {
        console.error('Unhandled promise rejection:', e.reason);
        // Track promise rejections
        trackEvent('promise_rejection', {
            reason: e.reason
        });
    });
}

/**
 * Initialize service worker for PWA functionality
 */
function initializeServiceWorker() {
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/sw.js')
            .then(registration => {
                console.log('Service Worker registered:', registration);
            })
            .catch(error => {
                console.log('Service Worker registration failed:', error);
            });
    }
}

/**
 * Initialize all monitoring and analytics
 */
function initializeMonitoring() {
    initializePerformanceMonitoring();
    initializeAnalytics();
    initializeErrorHandling();
    initializeServiceWorker();
}

// Initialize monitoring when DOM is loaded
document.addEventListener('DOMContentLoaded', initializeMonitoring);

// Export functions for external use
window.AttendrixLanding = {
    scrollToSection: function(sectionId) {
        const section = document.querySelector(sectionId);
        if (section) {
            section.scrollIntoView({ behavior: 'smooth' });
        }
    },
    
    showModal: function(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.add('show');
            modal.style.display = 'block';
            document.body.classList.add('modal-open');
        }
    },
    
    closeModal: function(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.remove('show');
            modal.style.display = 'none';
            document.body.classList.remove('modal-open');
        }
    },
    
    trackEvent: trackEvent
};

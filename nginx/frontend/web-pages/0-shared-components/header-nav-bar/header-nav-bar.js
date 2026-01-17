import { getLoginState, getLanguage, getCompanyPublishState, setLanguage, setLoginState, checkAuthStatus, checkCompanyStatus } from '../utils/shared-functions.js';

// ============================================
// ASYNC INITIALIZATION ON PAGE LOAD
// ============================================
document.addEventListener('DOMContentLoaded', async () => {
    // STEP 1: Check authentication status by calling the backend
    const isLoggedIn = await checkAuthStatus();
    
    // STEP 2: If logged in, check if user has a published company
    if (isLoggedIn) {
        await checkCompanyStatus();
    }
    
    // STEP 3: Now that we have accurate state, render the navigation bar
    renderNav();
    
    // STEP 4: Listen for state changes (from other tabs or same tab)
    document.addEventListener('stateChange', () => {
        console.log('[Nav] State changed, re-rendering navigation');
        renderNav();
    });
});

// ============================================
// TRANSLATIONS
// ============================================
const translations = {
    es: {
        profileView: "Ver perfil",
        companyEdit: "Editar empresa",
        logout: "Cerrar sesión",
        register: "Regístrate",
        login: "Inicia sesión",
        publish: "Publícate",
        flag: "us",
        img: "/files/logos/us.svg"
    },
    en: {
        profileView: "See profile",
        companyEdit: "Edit company",
        logout: "Log out",
        register: "Sign up",
        login: "Log in",
        publish: "Post Ad",
        flag: "es",
        img: "/files/logos/es.svg"
    }
};

// ============================================
// RENDER NAVIGATION BAR
// ============================================
function renderNav() {
    const navContainer = document.getElementById('nav-container-component');
    const lang = getLanguage();
    const isLoggedIn = getLoginState();
    const hasCompany = getCompanyPublishState();

    // Clear container safely
    navContainer.textContent = '';

    // Create nav element
    const nav = document.createElement('nav');
    nav.className = 'nav-container-flex-container';

    // Logo container
    const logoContainer = document.createElement('div');
    logoContainer.className = 'nav-container-logo-container';
    
    const logoLink = document.createElement('a');
    logoLink.href = 'http://localhost/front-page/front-page.html';
    
    const logoImg = document.createElement('img');
    logoImg.src = '/files/logos/logoSVG.svg';
    logoImg.alt = 'Proveo Logo';
    
    logoLink.appendChild(logoImg);
    logoContainer.appendChild(logoLink);
    nav.appendChild(logoContainer);

    // Navigation menu
    const ul = document.createElement('ul');
    ul.className = 'nav-container-ul';

    if (isLoggedIn) {
        // Profile link
        const profileLi = document.createElement('li');
        profileLi.className = 'nav-container-li';
        const profileLink = document.createElement('a');
        profileLink.href = 'http://localhost/profile-view/profile-view.html';
        profileLink.className = 'nav-container-a';
        profileLink.textContent = translations[lang].profileView;
        profileLi.appendChild(profileLink);
        ul.appendChild(profileLi);

        // Edit company OR publish link
        if (hasCompany) {
            const editLi = document.createElement('li');
            editLi.className = 'nav-container-li';
            const editLink = document.createElement('a');
            editLink.href = 'http://localhost/profile-edit/profile-edit.html';
            editLink.className = 'nav-container-a';
            editLink.textContent = translations[lang].companyEdit;
            editLi.appendChild(editLink);
            ul.appendChild(editLi);
        } else {
            const publishLi = document.createElement('li');
            publishLi.className = 'nav-container-li';
            const publishLink = document.createElement('a');
            publishLink.href = 'http://localhost/publish/publish.html';
            publishLink.className = 'nav-container-a';
            publishLink.textContent = translations[lang].publish;
            publishLi.appendChild(publishLink);
            ul.appendChild(publishLi);
        }

        // Logout link
        const logoutLi = document.createElement('li');
        logoutLi.className = 'nav-container-li';
        const logoutLink = document.createElement('a');
        logoutLink.href = '#';
        logoutLink.className = 'nav-container-a logout-link';
        logoutLink.textContent = translations[lang].logout;
        logoutLi.appendChild(logoutLink);
        ul.appendChild(logoutLi);
    } else {
        // Register link
        const registerLi = document.createElement('li');
        registerLi.className = 'nav-container-li';
        const registerLink = document.createElement('a');
        registerLink.href = 'http://localhost/sign-up/sign-up.html';
        registerLink.className = 'nav-container-a';
        registerLink.textContent = translations[lang].register;
        registerLi.appendChild(registerLink);
        ul.appendChild(registerLi);

        // Login link
        const loginLi = document.createElement('li');
        loginLi.className = 'nav-container-li';
        const loginLink = document.createElement('a');
        loginLink.href = 'http://localhost/log-in/log-in.html';
        loginLink.className = 'nav-container-a';
        loginLink.textContent = translations[lang].login;
        loginLi.appendChild(loginLink);
        ul.appendChild(loginLi);
    }

    // Language toggle (always shown)
    const langLi = document.createElement('li');
    langLi.className = 'nav-container-li lang-toggle';
    
    const langBtn = document.createElement('button');
    langBtn.id = 'lang-btn';
    langBtn.className = 'lang-btn';
    
    const langImg = document.createElement('img');
    langImg.src = translations[lang].img;
    langImg.alt = translations[lang].flag;
    langImg.className = 'lang-flag';
    
    langBtn.appendChild(langImg);
    langLi.appendChild(langBtn);
    ul.appendChild(langLi);

    nav.appendChild(ul);
    navContainer.appendChild(nav);
}

// ============================================
// EVENT HANDLERS
// ============================================
document.addEventListener('DOMContentLoaded', () => {
    const navContainer = document.getElementById('nav-container-component');
    
    navContainer.addEventListener("click", async (e) => {
        // Handle language toggle
        const btn = e.target.closest("#lang-btn");
        if (btn) {
            const currentLang = getLanguage();
            const newLang = currentLang === "es" ? "en" : "es";
            setLanguage(newLang);
            renderNav();
            return;
        }
        
        // Handle logout
        const logoutLink = e.target.closest('.logout-link');
        if (logoutLink) {
            e.preventDefault();
            
            try {
                const response = await fetch('/api/v1/users/logout', {
                    method: 'POST',
                    credentials: 'include',
                    headers: {
                        'X-Correlation-ID': `logout_${Date.now()}`
                    }
                });
                
                if (response.ok) {
                    // Clear all authentication data
                    setLoginState(false);
                    window.location.href = '../front-page/front-page.html';
                }
            } catch (error) {
                console.error('Logout error:', error);
                // Force logout even if request fails
                setLoginState(false);
                window.location.href = '../front-page/front-page.html';
            }
        }
    });
});
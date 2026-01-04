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

    let navBarContent = getLoginState()
        ? `
            <nav class="nav-container-flex-container">
                <div class="nav-container-logo-container">
                    <a href="http://localhost/front-page/front-page.html">
                        <img src="/files/logos/logoSVG.svg" alt="Proveo Logo" >
                    </a>
                </div>
                <ul class="nav-container-ul">
                    <li class="nav-container-li"><a href="http://localhost/profile-view/profile-view.html" class="nav-container-a">${translations[lang].profileView}</a></li>
                    ${getCompanyPublishState() ? `<li class="nav-container-li"><a href="http://localhost/profile-edit/profile-edit.html" class="nav-container-a">${translations[lang].companyEdit}</a></li>` : ""}
                    ${!getCompanyPublishState() ? `<li class="nav-container-li"><a href="http://localhost/publish/publish.html" class="nav-container-a">${translations[lang].publish}</a></li>` : ""}
                    <li class="nav-container-li"><a href="#" class="nav-container-a">${translations[lang].logout}</a></li>
                    <li class="nav-container-li lang-toggle">
                        <button id="lang-btn" class="lang-btn">
                            <img src="${translations[lang].img}" alt="${translations[lang].flag}" class="lang-flag">
                        </button>
                    </li>
                </ul>
            </nav>`
        : `
            <nav class="nav-container-flex-container">
                <div class="nav-container-logo-container">
                    <a href="http://localhost/front-page/front-page.html">
                        <img src="/files/logos/logoSVG.svg" alt="Proveo Logo" >
                    </a>
                </div>
                <ul class="nav-container-ul">
                    <li class="nav-container-li"><a href="http://localhost/sign-up/sign-up.html" class="nav-container-a">${translations[lang].register}</a></li>
                    <li class="nav-container-li"><a href="http://localhost/log-in/log-in.html" class="nav-container-a">${translations[lang].login}</a></li>
                    <li class="nav-container-li"><a href="http://localhost/publish/publish.html" class="nav-container-a">${translations[lang].publish}</a></li>
                    <li class="nav-container-li lang-toggle">
                        <button id="lang-btn" class="lang-btn">
                            <img src="${translations[lang].img}" alt="${translations[lang].flag}" class="lang-flag">
                        </button>
                    </li>
                </ul>
            </nav>`;

    navContainer.innerHTML = navBarContent;
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
        const logoutLink = e.target.closest('a[href="#"]');
        if (logoutLink && (logoutLink.textContent.includes('Cerrar sesión') || logoutLink.textContent.includes('Log out'))) {
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
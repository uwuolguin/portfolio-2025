import { getLoginState, getLanguage, getCompanyPublishState, setLanguage, setLoginState, checkAuthStatus, checkCompanyStatus } from '../utils/shared-functions.js';

document.addEventListener('DOMContentLoaded', async () => {
    const isLoggedIn = await checkAuthStatus();
    if (isLoggedIn) {
        await checkCompanyStatus();
    }
    renderNav();
});
document.addEventListener('DOMContentLoaded', () => {
    const navContainer = document.getElementById('nav-container-component');
    
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


    function renderNav() {
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

    navContainer.addEventListener("click", async (e) => {
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
        if (logoutLink && logoutLink.textContent.includes('Cerrar sesión') || logoutLink.textContent.includes('Log out')) {
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

    renderNav();
});
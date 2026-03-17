import { getInternalUrl, getLoginState, getLanguage, getCompanyPublishState, setLanguage, setLoginState, checkAuthStatus, checkCompanyStatus } from '../utils/shared-functions.js';

document.addEventListener('DOMContentLoaded', async () => {
    const isLoggedIn = await checkAuthStatus();
    if (isLoggedIn) {
        await checkCompanyStatus();
    }
    renderNav();
    document.addEventListener('stateChange', () => {
        renderNav();
    });
});

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
    const navContainer = document.getElementById('nav-container-component');
    const lang = getLanguage();
    const isLoggedIn = getLoginState();
    const hasCompany = getCompanyPublishState();

    navContainer.textContent = '';

    const nav = document.createElement('nav');
    nav.className = 'nav-container-flex-container';

    const logoContainer = document.createElement('div');
    logoContainer.className = 'nav-container-logo-container';
    const logoLink = document.createElement('a');
    logoLink.href = getInternalUrl('/front-page/front-page.html');
    const logoImg = document.createElement('img');
    logoImg.src = '/files/logos/logoSVG.svg';
    logoImg.alt = 'Proveo Logo';
    logoLink.appendChild(logoImg);
    logoContainer.appendChild(logoLink);
    nav.appendChild(logoContainer);

    const ul = document.createElement('ul');
    ul.className = 'nav-container-ul';

    if (isLoggedIn) {
        const profileLi = document.createElement('li');
        profileLi.className = 'nav-container-li';
        const profileLink = document.createElement('a');
        profileLink.href = getInternalUrl('/profile-view/profile-view.html');
        profileLink.className = 'nav-container-a';
        profileLink.textContent = translations[lang].profileView;
        profileLi.appendChild(profileLink);
        ul.appendChild(profileLi);

        if (hasCompany) {
            const editLi = document.createElement('li');
            editLi.className = 'nav-container-li';
            const editLink = document.createElement('a');
            editLink.href = getInternalUrl('/profile-edit/profile-edit.html');
            editLink.className = 'nav-container-a';
            editLink.textContent = translations[lang].companyEdit;
            editLi.appendChild(editLink);
            ul.appendChild(editLi);
        } else {
            const publishLi = document.createElement('li');
            publishLi.className = 'nav-container-li';
            const publishLink = document.createElement('a');
            publishLink.href = getInternalUrl('/publish/publish.html');
            publishLink.className = 'nav-container-a';
            publishLink.textContent = translations[lang].publish;
            publishLi.appendChild(publishLink);
            ul.appendChild(publishLi);
        }

        const logoutLi = document.createElement('li');
        logoutLi.className = 'nav-container-li';
        const logoutLink = document.createElement('a');
        logoutLink.href = '#';
        logoutLink.className = 'nav-container-a logout-link';
        logoutLink.textContent = translations[lang].logout;
        logoutLi.appendChild(logoutLink);
        ul.appendChild(logoutLi);
    } else {
        const registerLi = document.createElement('li');
        registerLi.className = 'nav-container-li';
        const registerLink = document.createElement('a');
        registerLink.href = getInternalUrl('/sign-up/sign-up.html');
        registerLink.className = 'nav-container-a';
        registerLink.textContent = translations[lang].register;
        registerLi.appendChild(registerLink);
        ul.appendChild(registerLi);

        const loginLi = document.createElement('li');
        loginLi.className = 'nav-container-li';
        const loginLink = document.createElement('a');
        loginLink.href = getInternalUrl('/log-in/log-in.html');
        loginLink.className = 'nav-container-a';
        loginLink.textContent = translations[lang].login;
        loginLi.appendChild(loginLink);
        ul.appendChild(loginLi);
    }

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

document.addEventListener('DOMContentLoaded', () => {
    const navContainer = document.getElementById('nav-container-component');

    navContainer.addEventListener("click", async (e) => {
        const btn = e.target.closest("#lang-btn");
        if (btn) {
            const currentLang = getLanguage();
            const newLang = currentLang === "es" ? "en" : "es";
            setLanguage(newLang);
            renderNav();
            return;
        }

        const logoutLink = e.target.closest('.logout-link');
        if (logoutLink) {
            e.preventDefault();
            try {
                const response = await fetch('/api/v1/users/logout', {
                    method: 'POST',
                    credentials: 'include',
                    headers: {
                        'X-Correlation-ID': `logout_${Date.now()}`,
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ lang: getLanguage() })
                });
                if (response.ok) {
                    setLoginState(false);
                    window.location.href = getInternalUrl('/front-page/front-page.html');
                }
            } catch (error) {
                console.error('Logout error:', error);
                setLoginState(false);
                window.location.href = getInternalUrl('/front-page/front-page.html');
            }
        }
    });
});

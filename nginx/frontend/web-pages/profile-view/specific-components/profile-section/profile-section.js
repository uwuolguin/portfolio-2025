import {
    getLanguage,
    apiRequest,
    getLoginState,
    setLoginState
} from '../../../0-shared-components/utils/shared-functions.js';

import {
    sanitizeText,
    sanitizeURL,
    sanitizeEmail,
    sanitizePhone,
    sanitizeAPIResponse  //  ADDED
} from '../../../0-shared-components/utils/sanitizer.js';

document.addEventListener('DOMContentLoaded', async () => {
    const profileContainer = document.getElementById('profile-section-container');

    const translations = {
        es: {
            welcome: 'Bienvenido',
            myProfile: 'Mi Perfil',
            myCompany: 'Mi Empresa',
            name: 'Nombre',
            email: 'Correo',
            phone: 'Teléfono',
            address: 'Dirección',
            commune: 'Comuna',
            product: 'Producto',
            description: 'Descripción',
            website: 'Sitio Web',
            noCompany: 'No tienes una empresa registrada',
            editProfile: 'Editar Perfil',
            editCompany: 'Editar Empresa',
            logout: 'Cerrar Sesión',
            loading: 'Cargando...',
            error: 'Error al cargar los datos'
        },
        en: {
            welcome: 'Welcome',
            myProfile: 'My Profile',
            myCompany: 'My Company',
            name: 'Name',
            email: 'Email',
            phone: 'Phone',
            address: 'Address',
            commune: 'Commune',
            product: 'Product',
            description: 'Description',
            website: 'Website',
            noCompany: 'You don\'t have a registered company',
            editProfile: 'Edit Profile',
            editCompany: 'Edit Company',
            logout: 'Logout',
            loading: 'Loading...',
            error: 'Error loading data'
        }
    };

    //  CRITICAL FIX: Sanitize fetched user data
    async function fetchUserData() {
        try {
            const response = await apiRequest('/api/v1/users/me');
            const rawData = await response.json();
            return sanitizeAPIResponse(rawData);
        } catch (error) {
            console.error('Error fetching user data:', error);
            return null;
        }
    }

    //  CRITICAL FIX: Sanitize fetched company data
    async function fetchMyCompany() {
        try {
            const response = await apiRequest('/api/v1/companies/user/my-company');
            const rawData = await response.json();
            return sanitizeAPIResponse(rawData);
        } catch (error) {
            console.error('Error fetching company data:', error);
            return null;
        }
    }

    async function renderProfile() {
        const lang = getLanguage();
        const t = translations[lang];

        profileContainer.innerHTML = `<div class="loading">${t.loading}</div>`;

        const userData = await fetchUserData();
        const companyData = await fetchMyCompany();

        if (!userData) {
            profileContainer.innerHTML = `<div class="error">${t.error}</div>`;
            return;
        }

        profileContainer.innerHTML = '';

        const profileSection = document.createElement('div');
        profileSection.className = 'profile-section';

        // Welcome header
        const welcomeHeader = document.createElement('h2');
        welcomeHeader.className = 'welcome-header';
        //  FIXED: Data already sanitized from fetchUserData
        welcomeHeader.textContent = `${t.welcome}, ${userData.name}`;
        profileSection.appendChild(welcomeHeader);

        // User profile card
        const userCard = createUserCard(userData, t);
        profileSection.appendChild(userCard);

        // Company card
        if (companyData) {
            const companyCard = createCompanyCard(companyData, t);
            profileSection.appendChild(companyCard);
        } else {
            const noCompanyMessage = document.createElement('div');
            noCompanyMessage.className = 'no-company-message';
            noCompanyMessage.textContent = t.noCompany;
            profileSection.appendChild(noCompanyMessage);
        }

        // Action buttons
        const actionsContainer = document.createElement('div');
        actionsContainer.className = 'profile-actions';

        const editProfileButton = document.createElement('button');
        editProfileButton.className = 'btn-primary';
        editProfileButton.textContent = t.editProfile;
        editProfileButton.addEventListener('click', () => {
            window.location.href = '/profile-edit';
        });

        const logoutButton = document.createElement('button');
        logoutButton.className = 'btn-secondary';
        logoutButton.textContent = t.logout;
        logoutButton.addEventListener('click', handleLogout);

        actionsContainer.appendChild(editProfileButton);
        actionsContainer.appendChild(logoutButton);
        profileSection.appendChild(actionsContainer);

        profileContainer.appendChild(profileSection);
    }

    function createUserCard(user, t) {
        const card = document.createElement('div');
        card.className = 'user-card';

        const title = document.createElement('h3');
        title.textContent = t.myProfile;
        card.appendChild(title);

        // FIXED: Data already sanitized
        const fields = [
            { label: t.name, value: user.name },
            { label: t.email, value: user.email }
        ];

        fields.forEach(field => {
            const fieldDiv = document.createElement('div');
            fieldDiv.className = 'profile-field';

            const label = document.createElement('span');
            label.className = 'field-label';
            label.textContent = field.label + ':';

            const value = document.createElement('span');
            value.className = 'field-value';
            value.textContent = field.value;

            fieldDiv.appendChild(label);
            fieldDiv.appendChild(value);
            card.appendChild(fieldDiv);
        });

        return card;
    }

    function createCompanyCard(company, t) {
        const card = document.createElement('div');
        card.className = 'company-card';

        const title = document.createElement('h3');
        title.textContent = t.myCompany;
        card.appendChild(title);

        //  FIXED: Data already sanitized
        const fields = [
            { label: t.name, value: company.name },
            { label: t.email, value: company.contact_email },
            { label: t.phone, value: company.contact_phone },
            { label: t.address, value: company.address },
            { label: t.commune, value: company.commune_name },
            { label: t.product, value: company.product_name },
            { label: t.description, value: company.description }
        ];

        fields.forEach(field => {
            if (field.value) {
                const fieldDiv = document.createElement('div');
                fieldDiv.className = 'profile-field';

                const label = document.createElement('span');
                label.className = 'field-label';
                label.textContent = field.label + ':';

                const value = document.createElement('span');
                value.className = 'field-value';
                value.textContent = field.value;

                fieldDiv.appendChild(label);
                fieldDiv.appendChild(value);
                card.appendChild(fieldDiv);
            }
        });

        if (company.website) {
            const websiteDiv = document.createElement('div');
            websiteDiv.className = 'profile-field';

            const label = document.createElement('span');
            label.className = 'field-label';
            label.textContent = t.website + ':';

            const link = document.createElement('a');
            link.href = company.website;
            link.textContent = company.website;
            link.target = '_blank';
            link.rel = 'noopener noreferrer';

            websiteDiv.appendChild(label);
            websiteDiv.appendChild(link);
            card.appendChild(websiteDiv);
        }

        return card;
    }

    async function handleLogout() {
        try {
            await apiRequest('/api/v1/auth/logout', { method: 'POST' });
            setLoginState(false);
            window.location.href = '/';
        } catch (error) {
            console.error('Logout error:', error);
            alert('Error logging out');
        }
    }

    await renderProfile();

    document.addEventListener('languageChange', renderProfile);
});
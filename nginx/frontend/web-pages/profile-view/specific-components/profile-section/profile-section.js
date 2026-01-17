import {
    getLanguage,
    getLoginState,
    apiRequest,
    setLoginState
} from '../../../0-shared-components/utils/shared-functions.js';

import {
    sanitizeText,
    setText,
    sanitizeAPIResponse,
    clearElement,
    setSrc
} from '../../../0-shared-components/utils/sanitizer.js';

document.addEventListener('DOMContentLoaded', async () => {
    const profileSection = document.getElementById('profile-section');

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
            noCompany: 'No tienes una empresa registrada',
            editCompany: 'Editar Empresa',
            createCompany: 'Publicar Empresa',
            deleteAccount: 'Eliminar Cuenta',
            logout: 'Cerrar Sesión',
            loading: 'Cargando...',
            error: 'Error al cargar los datos',
            deleteConfirm: '¿Estás seguro de que deseas eliminar tu cuenta? Esta acción no se puede deshacer.',
            deleteSuccess: 'Cuenta eliminada exitosamente',
            deleteError: 'Error al eliminar la cuenta',
            loginRequired: 'Debes iniciar sesión para ver tu perfil',
            loginHere: 'Iniciar sesión aquí',
            registerHere: 'Regístrate aquí',
            noAccount: '¿No tienes cuenta?'
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
            noCompany: 'You don\'t have a registered company',
            editCompany: 'Edit Company',
            createCompany: 'Publish Company',
            deleteAccount: 'Delete Account',
            logout: 'Logout',
            loading: 'Loading...',
            error: 'Error loading data',
            deleteConfirm: 'Are you sure you want to delete your account? This action cannot be undone.',
            deleteSuccess: 'Account deleted successfully',
            deleteError: 'Error deleting account',
            loginRequired: 'You must log in to view your profile',
            loginHere: 'Log in here',
            registerHere: 'Sign up here',
            noAccount: 'Don\'t have an account?'
        }
    };

    async function fetchUserData() {
        try {
            const response = await apiRequest('/api/v1/users/me');
            if (response.ok) {
                const rawData = await response.json();
                return sanitizeAPIResponse(rawData);
            }
            return null;
        } catch (error) {
            console.error('Error fetching user data:', error);
            return null;
        }
    }

    async function fetchMyCompany() {
        try {
            const response = await apiRequest('/api/v1/companies/user/my-company');
            if (response.ok) {
                const rawData = await response.json();
                return sanitizeAPIResponse(rawData);
            }
            return null;
        } catch (error) {
            console.error('Error fetching company data:', error);
            return null;
        }
    }

    async function renderProfile() {
        const lang = getLanguage() || 'es';
        const t = translations[lang] || translations.es;

        // ============================================
        // CHECK AUTHENTICATION FIRST
        // ============================================
        const isLoggedIn = getLoginState();
        
        if (!isLoggedIn) {
            clearElement(profileSection);
            
            const container = document.createElement('div');
            container.className = 'profile-container';
            
            const title = document.createElement('h2');
            title.className = 'profile-title';
            setText(title, t.myProfile);
            container.appendChild(title);
            
            const message = document.createElement('p');
            message.className = 'login-message';
            setText(message, t.loginRequired);
            container.appendChild(message);
            
            const actionsDiv = document.createElement('div');
            actionsDiv.className = 'profile-actions';
            actionsDiv.style.marginTop = '2rem';
            
            const loginButton = document.createElement('a');
            loginButton.href = '/log-in/log-in.html';
            loginButton.className = 'profile-button update-button';
            setText(loginButton, t.loginHere);
            loginButton.style.textDecoration = 'none';
            loginButton.style.display = 'inline-block';
            actionsDiv.appendChild(loginButton);
            
            container.appendChild(actionsDiv);
            
            const signupSection = document.createElement('div');
            signupSection.style.marginTop = '1.5rem';
            signupSection.style.color = '#ffffff';
            
            const noAccountText = document.createTextNode(t.noAccount + ' ');
            signupSection.appendChild(noAccountText);
            
            const signupLink = document.createElement('a');
            signupLink.href = '/sign-up/sign-up.html';
            setText(signupLink, t.registerHere);
            signupLink.style.color = '#FF9800';
            signupLink.style.textDecoration = 'none';
            signupSection.appendChild(signupLink);
            
            container.appendChild(signupSection);
            profileSection.appendChild(container);
            
            return; // BLOCK EXECUTION HERE
        }

        clearElement(profileSection);
        const loadingDiv = document.createElement('div');
        loadingDiv.className = 'loading';
        loadingDiv.style.color = 'white';
        loadingDiv.style.textAlign = 'center';
        loadingDiv.style.padding = '2rem';
        setText(loadingDiv, t.loading);
        profileSection.appendChild(loadingDiv);

        const userData = await fetchUserData();
        const companyData = await fetchMyCompany();

        clearElement(profileSection);

        if (!userData) {
            const errorDiv = document.createElement('div');
            errorDiv.className = 'error';
            errorDiv.style.color = 'white';
            errorDiv.style.textAlign = 'center';
            errorDiv.style.padding = '2rem';
            setText(errorDiv, t.error);
            profileSection.appendChild(errorDiv);
            return;
        }

        const container = document.createElement('div');
        container.className = 'profile-container';

        const title = document.createElement('h2');
        title.className = 'profile-title';
        setText(title, `${t.welcome}, ${sanitizeText(userData.name || '')}`);
        container.appendChild(title);

        const content = document.createElement('div');
        content.className = 'profile-content';

        const userDetails = document.createElement('div');
        userDetails.className = 'user-details';
        
        const userName = document.createElement('div');
        userName.className = 'user-name';
        setText(userName, userData.name || '');
        userDetails.appendChild(userName);
        
        const userEmail = document.createElement('div');
        userEmail.className = 'user-email';
        setText(userEmail, userData.email || '');
        userDetails.appendChild(userEmail);
        
        content.appendChild(userDetails);

        if (companyData) {
            const companySection = document.createElement('div');
            companySection.className = 'profile-info';
            
            const companyTitle = document.createElement('h3');
            companyTitle.style.color = '#FF9800';
            companyTitle.style.marginBottom = '1rem';
            setText(companyTitle, t.myCompany);
            companySection.appendChild(companyTitle);

            const imgUrl = companyData.image_url;
            if (imgUrl) {
                const imgContainer = document.createElement('div');
                imgContainer.style.marginBottom = '1rem';
                
                const img = document.createElement('img');
                img.className = 'company-image-preview';
                img.style.maxWidth = '100%';
                img.style.borderRadius = '8px';
                setSrc(img, imgUrl);
                img.alt = sanitizeText(companyData.name || 'Company image');
                img.onerror = function() {
                    this.style.display = 'none';
                };
                imgContainer.appendChild(img);
                companySection.appendChild(imgContainer);
            }

            const infoItems = [
                { label: t.name, value: companyData.name },
                { label: t.email, value: companyData.email },
                { label: t.phone, value: companyData.phone },
                { label: t.address, value: companyData.address },
                { label: t.commune, value: companyData.commune_name },
                { label: t.product, value: companyData.product_name_es || companyData.product_name_en },
                { label: t.description, value: lang === 'es' ? companyData.description_es : companyData.description_en }
            ];

            infoItems.forEach(item => {
                if (item.value) {
                    const infoItem = document.createElement('div');
                    infoItem.className = 'info-item';
                    
                    const label = document.createElement('span');
                    label.className = 'info-label';
                    setText(label, item.label);
                    
                    const value = document.createElement('span');
                    value.className = 'info-value';
                    setText(value, item.value);
                    
                    infoItem.appendChild(label);
                    infoItem.appendChild(value);
                    companySection.appendChild(infoItem);
                }
            });

            content.appendChild(companySection);
        } else {
            const noCompanyDiv = document.createElement('div');
            noCompanyDiv.className = 'info-item';
            noCompanyDiv.style.textAlign = 'center';
            
            const noCompanyText = document.createElement('p');
            noCompanyText.style.color = '#a0a0a0';
            setText(noCompanyText, t.noCompany);
            noCompanyDiv.appendChild(noCompanyText);
            
            content.appendChild(noCompanyDiv);
        }

        container.appendChild(content);

        const actionsDiv = document.createElement('div');
        actionsDiv.className = 'profile-actions';

        if (companyData) {
            const editButton = document.createElement('button');
            editButton.className = 'profile-button update-button';
            setText(editButton, t.editCompany);
            editButton.addEventListener('click', () => {
                window.location.href = '/profile-edit/profile-edit.html';
            });
            actionsDiv.appendChild(editButton);
        } else {
            const createButton = document.createElement('button');
            createButton.className = 'profile-button update-button';
            setText(createButton, t.createCompany);
            createButton.addEventListener('click', () => {
                window.location.href = '/publish/publish.html';
            });
            actionsDiv.appendChild(createButton);
        }

        const deleteButton = document.createElement('button');
        deleteButton.className = 'profile-button delete-button';
        setText(deleteButton, t.deleteAccount);
        deleteButton.addEventListener('click', async () => {
            if (confirm(t.deleteConfirm)) {
                try {
                    const response = await apiRequest('/api/v1/users/me', {
                        method: 'DELETE'
                    });

                    if (response.ok) {
                        alert(t.deleteSuccess);
                        setLoginState(false);
                        window.location.href = '/front-page/front-page.html';
                    } else {
                        const error = await response.json();
                        throw new Error(error.detail || t.deleteError);
                    }
                } catch (error) {
                    console.error('Delete error:', error);
                    alert(sanitizeText(error.message) || t.deleteError);
                }
            }
        });
        actionsDiv.appendChild(deleteButton);

        container.appendChild(actionsDiv);
        profileSection.appendChild(container);
    }

    await renderProfile();

    document.addEventListener('stateChange', renderProfile);
});
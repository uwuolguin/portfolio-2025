import { 
    getLanguage, 
    getLoginState, 
    getCompanyPublishState,
    apiRequest
} from '../../../0-shared-components/utils/shared-functions.js';
import { sanitizeText, sanitizeURL, sanitizeEmail, sanitizePhone } from '../../../0-shared-components/utils/sanitizer.js';

document.addEventListener('DOMContentLoaded', () => {
    const profileSection = document.getElementById('profile-section');

    const translations = {
        es: {
            title: "Mi Perfil",
            companyName: "Nombre de la empresa",
            productDescription: "Descripción del producto",
            address: "Dirección",
            phone: "Teléfono de la empresa",
            companyEmail: "Correo de la empresa",
            commune: "Comuna",
            productType: "Tipo de producto",
            companyImage: "Imagen de la empresa",
            loginRequired: "Debes iniciar sesión para ver tu perfil.",
            loginHere: "Inicia sesión aquí",
            noData: "No hay datos disponibles",
            noCompanyPublished: "Aún no has publicado una empresa.",
            publishCompanyHere: "Publica tu empresa aquí",
            publishFirst: "Para ver los datos de tu empresa, primero debes publicarla.",
            updateProfile: "Actualizar Perfil",
            deleteProfile: "Eliminar Perfil",
            confirmDelete: "¿Estás seguro de que quieres eliminar tu perfil? Esta acción no se puede deshacer.",
            profileDeleted: "Perfil eliminado exitosamente.",
            deleteError: "Error al eliminar el perfil. Inténtalo de nuevo."
        },
        en: {
            title: "My Profile",
            companyName: "Company name",
            productDescription: "Product description",
            address: "Address",
            phone: "Company phone",
            companyEmail: "Company email",
            commune: "Commune",
            productType: "Product type",
            companyImage: "Company image",
            loginRequired: "You must log in to view your profile.",
            loginHere: "Log in here",
            noData: "No data available",
            noCompanyPublished: "You haven't published a company yet.",
            publishCompanyHere: "Publish your company here",
            publishFirst: "To see your company data, you must publish it first.",
            updateProfile: "Update Profile",
            deleteProfile: "Delete Profile",
            confirmDelete: "Are you sure you want to delete your profile? This action cannot be undone.",
            profileDeleted: "Profile deleted successfully.",
            deleteError: "Error deleting profile. Please try again."
        }
    };

    async function fetchUserData() {
        try {
            const response = await apiRequest('/api/v1/users/me');
            if (response.ok) {
                return await response.json();
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
                return await response.json();
            } else if (response.status === 404) {
                return null;
            }
            return null;
        } catch (error) {
            console.error('Error fetching company:', error);
            return null;
        }
    }

    async function handleDeleteProfile() {
        const lang = getLanguage();
        const t = translations[lang];
        
        if (confirm(t.confirmDelete)) {
            try {
                const response = await apiRequest('/api/v1/users/me', {
                    method: 'DELETE'
                });

                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({}));
                    throw new Error(errorData.detail || 'Delete failed');
                }

                localStorage.clear();
                alert(t.profileDeleted);
                window.location.href = '../front-page/front-page.html';
                
            } catch (error) {
                console.error('Error deleting profile:', error);
                alert(t.deleteError + '\n' + error.message);
            }
        }
    }

    function createInfoItem(label, value) {
        const infoItem = document.createElement('div');
        infoItem.className = 'info-item';
        
        const labelEl = document.createElement('label');
        labelEl.className = 'info-label';
        labelEl.textContent = label;
        
        const valueEl = document.createElement('div');
        valueEl.className = 'info-value';
        valueEl.textContent = value;
        
        infoItem.appendChild(labelEl);
        infoItem.appendChild(valueEl);
        
        return infoItem;
    }

    async function renderProfileContent() {
        const lang = getLanguage();
        const t = translations[lang];
        const isLoggedIn = getLoginState();
        const hasPublishedCompany = getCompanyPublishState();

        profileSection.textContent = ''; // Clear

        const container = document.createElement('div');
        container.className = 'profile-container';

        const title = document.createElement('h2');
        title.className = 'profile-title';
        title.textContent = t.title;
        container.appendChild(title);

        // Case 1: Not logged in
        if (!isLoggedIn) {
            const message = document.createElement('div');
            message.className = 'login-message';
            message.textContent = t.loginRequired;
            
            const br = document.createElement('br');
            message.appendChild(br);
            message.appendChild(document.createElement('br'));
            
            const link = document.createElement('a');
            link.href = '../log-in/log-in.html';
            link.className = 'login-link';
            link.textContent = t.loginHere;
            message.appendChild(link);
            
            container.appendChild(message);
            profileSection.appendChild(container);
            return;
        }

        // Fetch user data
        const userData = await fetchUserData();
        
        if (!userData) {
            const message = document.createElement('div');
            message.className = 'login-message';
            message.textContent = 'Error loading profile data';
            container.appendChild(message);
            profileSection.appendChild(container);
            return;
        }

        // User details box (SANITIZED)
        const userDetails = document.createElement('div');
        userDetails.className = 'user-details';
        
        const userName = document.createElement('div');
        userName.className = 'user-name';
        userName.textContent = sanitizeText(userData.name); // SAFE
        
        const userEmail = document.createElement('div');
        userEmail.className = 'user-email';
        userEmail.textContent = sanitizeEmail(userData.email); // SAFE
        
        userDetails.appendChild(userName);
        userDetails.appendChild(userEmail);
        container.appendChild(userDetails);

        // Case 2: No company published
        if (!hasPublishedCompany) {
            const message = document.createElement('div');
            message.className = 'login-message';
            message.textContent = t.publishFirst;
            message.appendChild(document.createElement('br'));
            message.appendChild(document.createElement('br'));
            
            const link = document.createElement('a');
            link.href = '../publish/publish.html';
            link.className = 'login-link';
            link.textContent = t.publishCompanyHere;
            message.appendChild(link);
            
            container.appendChild(message);
            
            const actions = document.createElement('div');
            actions.className = 'profile-actions';
            
            const deleteBtn = document.createElement('button');
            deleteBtn.className = 'profile-button delete-button';
            deleteBtn.id = 'deleteProfileBtn';
            deleteBtn.textContent = t.deleteProfile;
            deleteBtn.addEventListener('click', handleDeleteProfile);
            
            actions.appendChild(deleteBtn);
            container.appendChild(actions);
            
            profileSection.appendChild(container);
            return;
        }
        
        // Case 3: Has company
        const companyData = await fetchMyCompany();
        
        if (!companyData) {
            setCompanyPublishState(false);
            renderProfileContent();
            return;
        }
        
        const profileContent = document.createElement('div');
        profileContent.className = 'profile-content';
        
        const profileInfo = document.createElement('div');
        profileInfo.className = 'profile-info';
        
        // Add all info items (SANITIZED)
        profileInfo.appendChild(createInfoItem(t.companyName, sanitizeText(companyData.name) || t.noData));
        profileInfo.appendChild(createInfoItem(t.productDescription, sanitizeText(lang === 'es' ? companyData.description_es : companyData.description_en) || t.noData));
        profileInfo.appendChild(createInfoItem(t.address, sanitizeText(companyData.address) || t.noData));
        profileInfo.appendChild(createInfoItem(t.phone, sanitizePhone(companyData.phone) || t.noData));
        profileInfo.appendChild(createInfoItem(t.companyEmail, sanitizeEmail(companyData.email) || t.noData));
        profileInfo.appendChild(createInfoItem(t.commune, sanitizeText(companyData.commune_name) || t.noData));
        profileInfo.appendChild(createInfoItem(t.productType, sanitizeText(lang === 'es' ? companyData.product_name_es : companyData.product_name_en) || t.noData));
        
        // Image item
        const imageItem = document.createElement('div');
        imageItem.className = 'info-item';
        
        const imageLabel = document.createElement('label');
        imageLabel.className = 'info-label';
        imageLabel.textContent = t.companyImage;
        imageItem.appendChild(imageLabel);
        
        if (companyData.image_url) {
            const img = document.createElement('img');
            img.src = sanitizeURL(companyData.image_url); // SAFE
            img.alt = 'Company Image';
            img.className = 'company-image-preview';
            imageItem.appendChild(img);
        } else {
            const noImage = document.createElement('div');
            noImage.className = 'info-value';
            noImage.textContent = t.noData;
            imageItem.appendChild(noImage);
        }
        
        profileInfo.appendChild(imageItem);
        profileContent.appendChild(profileInfo);
        container.appendChild(profileContent);
        
        // Action buttons
        const actions = document.createElement('div');
        actions.className = 'profile-actions';
        
        const updateBtn = document.createElement('button');
        updateBtn.className = 'profile-button update-button';
        updateBtn.textContent = t.updateProfile;
        updateBtn.addEventListener('click', () => {
            window.location.href = '../profile-edit/profile-edit.html';
        });
        
        const deleteBtn = document.createElement('button');
        deleteBtn.className = 'profile-button delete-button';
        deleteBtn.textContent = t.deleteProfile;
        deleteBtn.addEventListener('click', handleDeleteProfile);
        
        actions.appendChild(updateBtn);
        actions.appendChild(deleteBtn);
        container.appendChild(actions);
        
        profileSection.appendChild(container);
    }

    document.addEventListener('companyDataUpdated', renderProfileContent);
    document.addEventListener("languageChange", renderProfileContent);
    document.addEventListener("userHasLogged", renderProfileContent);
    document.addEventListener("companyPublishStateChange", renderProfileContent);
    renderProfileContent();
});
import { 
    getLanguage, 
    getLoginState, 
    getCompanyPublishState,
    getUserData,
    apiRequest
} from '../../../0-shared-components/utils/shared-functions.js';
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

    // Fetch real user data
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

    // Fetch user's company data
    async function fetchMyCompany() {
        try {
            const response = await apiRequest('/api/v1/companies/user/my-company');
            if (response.ok) {
                return await response.json();
            } else if (response.status === 404) {
                return null; // No company found
            }
            return null;
        } catch (error) {
            console.error('Error fetching company:', error);
            return null;
        }
    }

    // Function to get published company data
    function getPublishedCompanyData() {
        const stored = localStorage.getItem('publishedCompanyData');
        return stored ? JSON.parse(stored) : null;
    }

    function handleUpdateProfile() {
        const lang = getLanguage();
        console.log("Update profile clicked");
        alert(lang === 'es' ? 'Funcionalidad de actualizar perfil - TODO' : 'Update profile functionality - TODO');
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

                console.log("User account deleted");
                
                // Clear all local storage
                localStorage.clear();
                
                alert(t.profileDeleted);
                
                // Redirect to main page
                window.location.href = '../front-page/front-page.html';
                
            } catch (error) {
                console.error('Error deleting profile:', error);
                alert(t.deleteError + '\n' + error.message);
            }
        }
    }

    async function renderProfileContent() {
        const lang = getLanguage();
        const t = translations[lang];
        const isLoggedIn = getLoginState();
        const hasPublishedCompany = getCompanyPublishState();

        // Case 1: User NOT logged in
        if (!isLoggedIn) {
            profileSection.innerHTML = `
                <div class="profile-container">
                    <h2 class="profile-title">${t.title}</h2>
                    <div class="login-message">
                        ${t.loginRequired}
                        <br><br>
                        <a href="../log-in/log-in.html" class="login-link">${t.loginHere}</a>
                    </div>
                </div>
            `;
            return;
        }

        // Fetch real user data
        const userData = await fetchUserData();
        
        if (!userData) {
            profileSection.innerHTML = `
                <div class="profile-container">
                    <h2 class="profile-title">${t.title}</h2>
                    <div class="login-message">Error loading profile data</div>
                </div>
            `;
            return;
        }

        // Case 2: User logged in but hasn't published a company
        if (!hasPublishedCompany) {
            profileSection.innerHTML = `
                <div class="profile-container">
                    <h2 class="profile-title">${t.title}</h2>
                    <div class="user-details">
                        <div class="user-name">${userData.name}</div>
                        <div class="user-email">${userData.email}</div>
                    </div>
                    <div class="login-message">
                        ${t.publishFirst}
                        <br><br>
                        <a href="../publish/publish.html" class="login-link">${t.publishCompanyHere}</a>
                    </div>
                    <div class="profile-actions">
                        <button class="profile-button delete-button" id="deleteProfileBtn">${t.deleteProfile}</button>
                    </div>
                </div>
            `;
            
            const deleteBtn = document.getElementById('deleteProfileBtn');
            if (deleteBtn) {
                deleteBtn.addEventListener('click', handleDeleteProfile);
            }
            
            return;
        }
        
        // Case 3: User logged in and has published a company
        const companyData = await fetchMyCompany();
        
        if (!companyData) {
            // If API says no company but localStorage says yes, sync the state
            setCompanyPublishState(false);
            renderProfileContent(); // Re-render
            return;
        }
        
        profileSection.innerHTML = `
            <div class="profile-container">
                <h2 class="profile-title">${t.title}</h2>
                <div class="profile-content">
                    <div class="user-details">
                        <div class="user-name">${userData.name}</div>
                        <div class="user-email">${userData.email}</div>
                    </div>
                    
                    <div class="profile-info">
                        <div class="info-item">
                            <label class="info-label">${t.companyName}</label>
                            <div class="info-value">${companyData.name || t.noData}</div>
                        </div>
                        
                        <div class="info-item">
                            <label class="info-label">${t.productDescription}</label>
                            <div class="info-value">${lang === 'es' ? companyData.description_es : companyData.description_en || t.noData}</div>
                        </div>
                        
                        <div class="info-item">
                            <label class="info-label">${t.address}</label>
                            <div class="info-value">${companyData.address || t.noData}</div>
                        </div>
                        
                        <div class="info-item">
                            <label class="info-label">${t.phone}</label>
                            <div class="info-value">${companyData.phone || t.noData}</div>
                        </div>
                        
                        <div class="info-item">
                            <label class="info-label">${t.companyEmail}</label>
                            <div class="info-value">${companyData.email || t.noData}</div>
                        </div>
                        
                        <div class="info-item">
                            <label class="info-label">${t.commune}</label>
                            <div class="info-value">${companyData.commune_name || t.noData}</div>
                        </div>
                        
                        <div class="info-item">
                            <label class="info-label">${t.productType}</label>
                            <div class="info-value">${lang === 'es' ? companyData.product_name_es : companyData.product_name_en || t.noData}</div>
                        </div>
                        
                        <div class="info-item">
                            <label class="info-label">${t.companyImage}</label>
                            ${companyData.image_url ? `
                                <img src="${companyData.image_url}" alt="Company Image" class="company-image-preview">
                            ` : `
                                <div class="info-value">${t.noData}</div>
                            `}
                        </div>
                    </div>
                </div>
                <div class="profile-actions">
                    <button class="profile-button update-button" id="updateProfileBtn">${t.updateProfile}</button>
                    <button class="profile-button delete-button" id="deleteProfileBtn">${t.deleteProfile}</button>
                </div>
            </div>
        `;

        // Add event listeners
        const updateBtn = document.getElementById('updateProfileBtn');
        const deleteBtn = document.getElementById('deleteProfileBtn');
        
        if (updateBtn) {
            updateBtn.addEventListener('click', () => {
                window.location.href = '../profile-edit/profile-edit.html';
            });
        }
        if (deleteBtn) {
            deleteBtn.addEventListener('click', handleDeleteProfile);
        }
    }

    // Listen for company data updates
    document.addEventListener('companyDataUpdated', renderProfileContent);
    document.addEventListener("languageChange", renderProfileContent);
    document.addEventListener("userHasLogged", renderProfileContent);
    document.addEventListener("companyPublishStateChange", renderProfileContent);
    renderProfileContent();
});
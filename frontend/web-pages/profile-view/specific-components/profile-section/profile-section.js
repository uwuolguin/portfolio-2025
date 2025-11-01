import { getLanguage, getLoginState, getCompanyPublishState } from '../../../0-shared-components/utils/shared-functions.js';

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

    // Mock user data - In a real app, this would come from an API
    const mockUserData = {
        name: "Juan Pérez",
        email: "juan.perez@email.com"
    };

    // Mock company data with example image for demonstration
    const mockCompanyDataWithImage = {
        companyName: "Panadería El Buen Pan",
        productDescription: "Elaboramos pan artesanal fresco todos los días, con ingredientes naturales y recetas tradicionales. Especialistas en pan integral, pasteles y productos de repostería.",
        address: "Av. Los Leones 1234, Providencia",
        phone: "+56 9 8765 4321",
        companyEmail: "contacto@elbuenpan.cl",
        commune: "Providencia",
        productType: "Panadería",
        companyImageBase64: "https://images.unsplash.com/photo-1509440159596-0249088772ff?ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D&auto=format&fit=crop&w=1000&q=80"
    };

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

    function handleDeleteProfile() {
        const lang = getLanguage();
        const t = translations[lang];
        
        if (confirm(t.confirmDelete)) {
            try {
                console.log("Deleting profile...");
                // Clear published company data
                localStorage.removeItem('publishedCompanyData');
                localStorage.setItem("isLoggedIn", "false");
                localStorage.setItem("hasPublishedCompany", "false");
                alert(t.profileDeleted);
                location.reload();
            } catch (error) {
                console.error('Error deleting profile:', error);
                alert(t.deleteError);
            }
        }
    }

    function renderProfileContent() {
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
                        <a href="../login/login.html" class="login-link">${t.loginHere}</a>
                    </div>
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
                        <div class="user-name">${mockUserData.name}</div>
                        <div class="user-email">${mockUserData.email}</div>
                    </div>
                    <div class="login-message">
                        ${t.publishFirst}
                        <br><br>
                        <a href="../publish/publish.html" class="login-link">${t.publishCompanyHere}</a>
                    </div>
                    <div class="profile-actions">
                        <button class="profile-button update-button" id="updateProfileBtn">${t.updateProfile}</button>
                        <button class="profile-button delete-button" id="deleteProfileBtn">${t.deleteProfile}</button>
                    </div>
                </div>
            `;
        } else {
            // Case 3: User logged in and has published a company
            const companyData = getPublishedCompanyData();
            
            // Use mock data with example image if no real data exists (for demonstration)
            const displayData = companyData || mockCompanyDataWithImage;
            
            profileSection.innerHTML = `
                <div class="profile-container">
                    <h2 class="profile-title">${t.title}</h2>
                    <div class="profile-content">
                        <div class="user-details">
                            <div class="user-name">${mockUserData.name}</div>
                            <div class="user-email">${mockUserData.email}</div>
                        </div>
                        
                        <div class="profile-info">
                            <div class="info-item">
                                <label class="info-label">${t.companyName}</label>
                                <div class="info-value">${displayData?.companyName || t.noData}</div>
                            </div>
                            
                            <div class="info-item">
                                <label class="info-label">${t.productDescription}</label>
                                <div class="info-value">${displayData?.productDescription || t.noData}</div>
                            </div>
                            
                            <div class="info-item">
                                <label class="info-label">${t.address}</label>
                                <div class="info-value">${displayData?.address || t.noData}</div>
                            </div>
                            
                            <div class="info-item">
                                <label class="info-label">${t.phone}</label>
                                <div class="info-value">${displayData?.phone || t.noData}</div>
                            </div>
                            
                            <div class="info-item">
                                <label class="info-label">${t.companyEmail}</label>
                                <div class="info-value">${displayData?.companyEmail || t.noData}</div>
                            </div>
                            
                            <div class="info-item">
                                <label class="info-label">${t.commune}</label>
                                <div class="info-value">${displayData?.commune || t.noData}</div>
                            </div>
                            
                            <div class="info-item">
                                <label class="info-label">${t.productType}</label>
                                <div class="info-value">${displayData?.productType || t.noData}</div>
                            </div>
                            
                            <div class="info-item">
                                <label class="info-label">${t.companyImage}</label>
                                ${displayData?.companyImageBase64 ? `
                                    <img src="${displayData.companyImageBase64}" alt="Company Image" class="company-image-preview">
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
        }

        // Add event listeners for buttons (only if user is logged in)
        if (isLoggedIn) {
            const updateBtn = document.getElementById('updateProfileBtn');
            const deleteBtn = document.getElementById('deleteProfileBtn');
            
            if (updateBtn) {
                updateBtn.addEventListener('click', handleUpdateProfile);
            }
            if (deleteBtn) {
                deleteBtn.addEventListener('click', handleDeleteProfile);
            }
        }
    }

    // Listen for company data updates
    document.addEventListener('companyDataUpdated', renderProfileContent);
    document.addEventListener("languageChange", renderProfileContent);
    document.addEventListener("userHasLogged", renderProfileContent);
    document.addEventListener("companyPublishStateChange", renderProfileContent);
    renderProfileContent();
});
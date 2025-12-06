import { 
    getLanguage, 
    getLoginState, 
    getCompanyPublishState, 
    setCompanyData,
    fetchProducts,
    fetchCommunes,
    apiRequest
} from '../../../0-shared-components/utils/shared-functions.js';

document.addEventListener('DOMContentLoaded', () => {
    const profileEditSection = document.getElementById('profile-edit-section');

    const translations = {
        es: {
            title: "Editar perfil de empresa",
            companyName: "Nombre de la empresa",
            productDescription: "Descripción del producto",
            address: "Dirección",
            phone: "Teléfono de la empresa",
            companyEmail: "Correo de la empresa",
            commune: "Comuna",
            productType: "Tipo de producto",
            updateButton: "Actualizar",
            cancelButton: "Cancelar",
            deleteButton: "Eliminar empresa",
            selectImage: "📷 Cambiar imagen de la empresa",
            currentImage: "Imagen actual:",
            noImage: "No hay imagen seleccionada",
            updateSuccess: "¡Perfil actualizado exitosamente!",
            updateError: "Error al actualizar el perfil. Inténtalo de nuevo.",
            deleteSuccess: "¡Empresa eliminada exitosamente!",
            deleteError: "Error al eliminar la empresa. Inténtalo de nuevo.",
            deleteConfirm: "¿Estás seguro de que deseas eliminar tu empresa? Esta acción no se puede deshacer.",
            loginRequired: "Debes iniciar sesión para editar tu perfil.",
            loginHere: "Inicia sesión aquí",
            noCompany: "No tienes una empresa publicada para editar.",
            publishCompany: "Publicar empresa",
            noCompanyMessage: "Primero debes publicar una empresa para poder editarla.",
            updating: "Actualizando...",
            deleting: "Eliminando...",
            searchCommunePlaceholder: "Buscar comuna...",
            searchProductPlaceholder: "Buscar producto...",
            loadingError: "Error al cargar los datos de la empresa."
        },
        en: {
            title: "Edit company profile",
            companyName: "Company name",
            productDescription: "Product description",
            address: "Address",
            phone: "Company phone",
            companyEmail: "Company email",
            commune: "Commune",
            productType: "Product type",
            updateButton: "Update",
            cancelButton: "Cancel",
            deleteButton: "Delete company",
            selectImage: "📷 Change company image",
            currentImage: "Current image:",
            noImage: "No image selected",
            updateSuccess: "Profile updated successfully!",
            updateError: "Error updating profile. Please try again.",
            deleteSuccess: "Company deleted successfully!",
            deleteError: "Error deleting company. Please try again.",
            deleteConfirm: "Are you sure you want to delete your company? This action cannot be undone.",
            loginRequired: "You must log in to edit your profile.",
            loginHere: "Log in here",
            noCompany: "You don't have a published company to edit.",
            publishCompany: "Publish company",
            noCompanyMessage: "You must publish a company first before you can edit it.",
            updating: "Updating...",
            deleting: "Deleting...",
            searchCommunePlaceholder: "Search commune...",
            searchProductPlaceholder: "Search product...",
            loadingError: "Error loading company data."
        }
    };

    // Fetch user's company data from backend
    async function fetchMyCompany() {
        try {
            const response = await apiRequest('/api/v1/companies/user/my-company');
            
            if (response.ok) {
                const company = await response.json();
                return company;
            } else if (response.status === 404) {
                return null; // No company found
            } else {
                throw new Error('Failed to fetch company');
            }
        } catch (error) {
            console.error('Error fetching company:', error);
            return null;
        }
    }

    // Simple filterable dropdown function
    function createFilterableDropdown(options, placeholder, className, id, defaultText, currentValue) {
        const selectedText = currentValue || defaultText;
        const dropdownHTML = `
            <div class="filterable-dropdown ${className}" data-dropdown-id="${id}">
                <div class="dropdown-selected" data-value="${currentValue || ''}">
                    ${selectedText}
                    <span class="dropdown-arrow">▼</span>
                </div>
                <div class="dropdown-options" style="display: none;">
                    <input type="text" class="dropdown-search" placeholder="${placeholder}" autocomplete="off">
                    <div class="options-list">
                        ${options.map(option => `
                            <div class="dropdown-option" data-value="${option}">${option}</div>
                        `).join('')}
                    </div>
                </div>
            </div>
        `;
        return dropdownHTML;
    }

    // Initialize dropdown functionality with dynamic push
    function initDropdowns() {
        const dropdowns = document.querySelectorAll('.filterable-dropdown');
        
        dropdowns.forEach(dropdown => {
            const selected = dropdown.querySelector('.dropdown-selected');
            const options = dropdown.querySelector('.dropdown-options');
            const search = dropdown.querySelector('.dropdown-search');
            const allOptions = dropdown.querySelectorAll('.dropdown-option');
            
            selected.addEventListener('click', (e) => {
                e.stopPropagation();
                
                // Close all dropdowns first and remove open classes
                document.querySelectorAll('.dropdown-options').forEach(opt => opt.style.display = 'none');
                document.querySelectorAll('.input-group').forEach(group => group.classList.remove('dropdown-open'));
                
                // Toggle current dropdown
                if (options.style.display === 'block') {
                    options.style.display = 'none';
                    dropdown.closest('.input-group').classList.remove('dropdown-open');
                } else {
                    options.style.display = 'block';
                    dropdown.closest('.input-group').classList.add('dropdown-open');
                    search.focus();
                    search.value = '';
                    allOptions.forEach(opt => opt.style.display = 'block');
                }
            });
            
            search.addEventListener('input', (e) => {
                const searchTerm = e.target.value.toLowerCase();
                allOptions.forEach(option => {
                    const text = option.textContent.toLowerCase();
                    option.style.display = text.includes(searchTerm) ? 'block' : 'none';
                });
            });
            
            allOptions.forEach(option => {
                option.addEventListener('click', () => {
                    selected.innerHTML = `${option.textContent} <span class="dropdown-arrow">▼</span>`;
                    selected.setAttribute('data-value', option.getAttribute('data-value'));
                    options.style.display = 'none';
                    dropdown.closest('.input-group').classList.remove('dropdown-open');
                });
            });
            
            options.addEventListener('click', (e) => e.stopPropagation());
        });
        
        // Close dropdowns when clicking outside
        document.addEventListener('click', () => {
            document.querySelectorAll('.dropdown-options').forEach(options => {
                options.style.display = 'none';
            });
            document.querySelectorAll('.input-group').forEach(group => {
                group.classList.remove('dropdown-open');
            });
        });
    }

    function renderLoginRequired() {
        const lang = getLanguage();
        const t = translations[lang];

        profileEditSection.innerHTML = `
            <div class="profile-edit-container">
                <h2 class="profile-edit-title">${t.title}</h2>
                <div class="login-message">
                    ${t.loginRequired}
                    <br><br>
                    <a href="../log-in/log-in.html">${t.loginHere}</a>
                </div>
            </div>
        `;
    }

    function renderNoCompany() {
        const lang = getLanguage();
        const t = translations[lang];

        profileEditSection.innerHTML = `
            <div class="profile-edit-container">
                <h2 class="profile-edit-title">${t.noCompany}</h2>
                <div class="no-company-message">${t.noCompanyMessage}</div>
                <div class="profile-edit-actions">
                    <button id="publishCompanyBtn" class="profile-edit-button">${t.publishCompany}</button>
                </div>
            </div>
        `;

        // Add event listeners
        document.getElementById('publishCompanyBtn').addEventListener('click', () => {
            window.location.href = '../publish/publish.html';
        });
    }

    async function renderEditForm() {
        const lang = getLanguage();
        const t = translations[lang];
        
        // Show loading state
        profileEditSection.innerHTML = `
            <div class="profile-edit-container">
                <h2 class="profile-edit-title">${t.title}</h2>
                <div class="login-message">${lang === 'es' ? 'Cargando...' : 'Loading...'}</div>
            </div>
        `;
        
        // Fetch real company data from backend
        const companyData = await fetchMyCompany();
        
        if (!companyData) {
            // If no company found, sync state and show no company view
            setCompanyPublishState(false);
            renderNoCompany();
            return;
        }
        
        // Fetch products and communes
        const products = await fetchProducts();
        const communes = await fetchCommunes();
        
        // Find current product and commune names
        const currentProduct = products.find(p => p.uuid === companyData.product_uuid);
        const currentCommune = communes.find(c => c.uuid === companyData.commune_uuid);
        
        const productNames = products.map(p => lang === 'es' ? p.name_es : p.name_en);
        const communeNames = communes.map(c => c.name);
        
        const currentProductName = currentProduct ? (lang === 'es' ? currentProduct.name_es : currentProduct.name_en) : null;
        const currentCommuneName = currentCommune ? currentCommune.name : null;

        const communeDropdown = createFilterableDropdown(
            communeNames, 
            t.searchCommunePlaceholder, 
            'commune-dropdown', 
            'commune',
            t.commune,
            currentCommuneName
        );
        
        const productDropdown = createFilterableDropdown(
            productNames, 
            t.searchProductPlaceholder, 
            'product-dropdown', 
            'product',
            t.productType,
            currentProductName
        );

        profileEditSection.innerHTML = `
            <div class="profile-edit-container">
                <h2 class="profile-edit-title">${t.title}</h2>
                <form id="profile-edit-form" class="profile-edit-form">
                    <div class="input-group">
                        <input type="text" id="companyName" class="profile-edit-input" placeholder="${t.companyName}" value="${companyData.name || ''}" required>
                    </div>
                    <div class="input-group">
                        <textarea id="productDescription" class="profile-edit-textarea" placeholder="${t.productDescription}" required>${lang === 'es' ? (companyData.description_es || '') : (companyData.description_en || '')}</textarea>
                    </div>
                    <div class="input-group">
                        <input type="text" id="address" class="profile-edit-input" placeholder="${t.address}" value="${companyData.address || ''}" required>
                    </div>
                    <div class="input-group">
                        <input type="tel" id="phone" class="profile-edit-input" placeholder="${t.phone}" value="${companyData.phone || ''}" required>
                    </div>
                    <div class="input-group">
                        <input type="email" id="companyEmail" class="profile-edit-input" placeholder="${t.companyEmail}" value="${companyData.email || ''}" required>
                    </div>
                    <div class="input-group">
                        ${communeDropdown}
                    </div>
                    <div class="input-group">
                        ${productDropdown}
                    </div>
                    <div class="input-group">
                        <div class="current-image-container">
                            <label class="current-image-label">${t.currentImage}</label>
                            ${companyData.image_url ?
                                `<img src="${companyData.image_url}" alt="Company Image" class="current-image">` :
                                `<div class="no-image-placeholder">${t.noImage}</div>`
                            }
                        </div>
                        <div class="file-input-wrapper">
                            <input type="file" id="companyImage" class="file-input-hidden" accept="image/*">
                            <label for="companyImage" class="file-input-label" id="fileLabel">
                                ${t.selectImage}
                            </label>
                        </div>
                    </div>
                    <div class="profile-edit-actions">
                        <button type="submit" class="profile-edit-button">${t.updateButton}</button>
                        <button type="button" id="cancelBtn" class="profile-edit-button secondary">${t.cancelButton}</button>
                        <button type="button" id="deleteBtn" class="profile-edit-button danger">${t.deleteButton}</button>
                    </div>
                </form>
            </div>
        `;

        initDropdowns();
        
        // Store company UUID for update/delete
        const companyUUID = companyData.uuid;

        const form = document.getElementById("profile-edit-form");
        form.addEventListener("submit", async (e) => {
            e.preventDefault();

            const communeValue = document.querySelector('[data-dropdown-id="commune"] .dropdown-selected').getAttribute('data-value');
            const productValue = document.querySelector('[data-dropdown-id="product"] .dropdown-selected').getAttribute('data-value');
            
            if (!communeValue) {
                alert(lang === 'es' ? 'Por favor selecciona una comuna' : 'Please select a commune');
                return;
            }
            
            if (!productValue) {
                alert(lang === 'es' ? 'Por favor selecciona un tipo de producto' : 'Please select a product type');
                return;
            }

            const submitButton = form.querySelector('button[type="submit"]');
            const originalButtonText = submitButton.textContent;

            submitButton.disabled = true;
            submitButton.textContent = t.updating;

            try {
                // Get products and communes to find UUIDs
                const products = await fetchProducts();
                const communes = await fetchCommunes();
                
                const selectedProduct = products.find(p => 
                    (lang === 'es' ? p.name_es : p.name_en) === productValue
                );
                const selectedCommune = communes.find(c => c.name === communeValue);
                
                if (!selectedProduct || !selectedCommune) {
                    throw new Error('Invalid product or commune selection');
                }
                
                const formData = new FormData();
                formData.append('name', document.getElementById("companyName").value);
                formData.append('product_uuid', selectedProduct.uuid);
                formData.append('commune_uuid', selectedCommune.uuid);
                formData.append('address', document.getElementById("address").value);
                formData.append('phone', document.getElementById("phone").value);
                formData.append('email', document.getElementById("companyEmail").value);
                formData.append('lang', lang);
                
                // Add description
                const description = document.getElementById("productDescription").value;
                if (lang === 'es') {
                    formData.append('description_es', description);
                } else {
                    formData.append('description_en', description);
                }

                const imageFile = document.getElementById("companyImage").files[0];
                if (imageFile) {
                    formData.append('image', imageFile);
                }

                const response = await apiRequest(`/api/v1/companies/${companyUUID}`, {
                    method: 'PUT',
                    body: formData
                });

                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({}));
                    throw new Error(errorData.detail || 'Update failed');
                }
                
                const updatedCompany = await response.json();
                
                console.log("Company updated:", updatedCompany);

                // Update local cache
                setCompanyData(updatedCompany);

                showMessage(t.updateSuccess, 'success');

                setTimeout(() => {
                    renderEditForm();
                }, 2000);

            } catch (error) {
                console.error('Error updating company:', error);
                showMessage(t.updateError + '\n' + error.message, 'error');
            } finally {
                submitButton.disabled = false;
                submitButton.textContent = originalButtonText;
            }
        });

        // Cancel button
        document.getElementById('cancelBtn').addEventListener('click', () => {
            window.location.href = '../profile-view/profile-view.html';
        });

        // Delete button
        document.getElementById('deleteBtn').addEventListener('click', async () => {
            if (confirm(t.deleteConfirm)) {
                const deleteButton = document.getElementById('deleteBtn');
                const originalButtonText = deleteButton.textContent;

                deleteButton.disabled = true;
                deleteButton.textContent = t.deleting;

                try {
                    const response = await apiRequest(`/api/v1/companies/${companyUUID}`, {
                        method: 'DELETE'
                    });

                    if (!response.ok) {
                        const errorData = await response.json().catch(() => ({}));
                        throw new Error(errorData.detail || 'Delete failed');
                    }

                    console.log("Company deleted");

                    // Clear company data and publish state
                    setCompanyData(null);

                    // Show success message
                    showMessage(t.deleteSuccess, 'success');

                    // Redirect to publish page after delay
                    setTimeout(() => {
                        window.location.href = '../publish/publish.html';
                    }, 2000);

                } catch (error) {
                    console.error('Error deleting company:', error);
                    showMessage(t.deleteError + '\n' + error.message, 'error');

                    deleteButton.disabled = false;
                    deleteButton.textContent = originalButtonText;
                }
            }
        });

        // File input handling
        const fileInput = document.getElementById("companyImage");
        const fileLabel = document.getElementById("fileLabel");

        fileInput.addEventListener("change", (e) => {
            const fileName = e.target.files[0]?.name;
            
            if (fileName) {
                fileLabel.textContent = `✅ ${fileName}`;
                fileLabel.classList.add("has-file");
            } else {
                fileLabel.textContent = t.selectImage;
                fileLabel.classList.remove("has-file");
            }
        });
    }

    function showMessage(message, type) {
        const container = document.querySelector('.profile-edit-container');
        const existingMessage = container.querySelector('.success-message, .error-message');

        if (existingMessage) {
            existingMessage.remove();
        }

        const messageDiv = document.createElement('div');
        messageDiv.className = type === 'success' ? 'success-message' : 'error-message';
        messageDiv.textContent = message;

        container.insertBefore(messageDiv, container.firstChild.nextSibling);

        // Auto-remove message after 5 seconds
        setTimeout(() => {
            if (messageDiv.parentNode) {
                messageDiv.remove();
            }
        }, 5000);
    }

    async function renderContent() {
        const isLoggedIn = getLoginState();
        const hasPublishedCompany = getCompanyPublishState();

        if (!isLoggedIn) {
            renderLoginRequired();
        } else if (!hasPublishedCompany) {
            renderNoCompany();
        } else {
            await renderEditForm();
        }
    }

    document.addEventListener("languageChange", renderContent);
    document.addEventListener("userHasLogged", renderContent);
    document.addEventListener("companyPublishStateChange", renderContent);
    document.addEventListener("companyDataChange", renderContent);
    
    renderContent();
});
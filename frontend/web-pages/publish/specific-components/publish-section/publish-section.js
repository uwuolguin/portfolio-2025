import { 
    getLanguage, 
    getLoginState, 
    getCompanyPublishState, 
    setCompanyPublishState,
    setCompanyData,
    fetchProducts,
    fetchCommunes,
    apiRequest
} from '../../../0-shared-components/utils/shared-functions.js';
document.addEventListener('DOMContentLoaded', () => {
    const publishSection = document.getElementById('publish-section');

    const translations = {
        es: {
            title: "Publica tu empresa",
            companyName: "Nombre de la empresa",
            productDescription: "Descripción del producto",
            address: "Dirección",
            phone: "Teléfono de la empresa",
            companyEmail: "Correo de la empresa",
            commune: "Comuna",
            productType: "Tipo de producto",
            publishButton: "Publicar",
            selectImage: "📷 Seleccionar imagen de la empresa",
            publishSuccess: "¡Empresa publicada exitosamente!",
            publishError: "Error al publicar la empresa. Inténtalo de nuevo.",
            loginRequired: "Debes iniciar sesión para publicar tu empresa.",
            loginHere: "Inicia sesión aquí",
            alreadyPublished: "Ya has publicado una empresa.",
            viewProfile: "Ver mi perfil",
            alreadyPublishedMessage: "Tu empresa ya está publicada.",
            searchCommunePlaceholder: "Buscar comuna...",
            searchProductPlaceholder: "Buscar producto...",
            loading: "Cargando...",
            imageRequired: "Por favor selecciona una imagen"
        },
        en: {
            title: "Publish your company",
            companyName: "Company name",
            productDescription: "Product description",
            address: "Address",
            phone: "Company phone",
            companyEmail: "Company email",
            commune: "Commune",
            productType: "Product type",
            publishButton: "Publish",
            selectImage: "📷 Select company image",
            publishSuccess: "Company published successfully!",
            publishError: "Error publishing company. Please try again.",
            loginRequired: "You must log in to publish your company.",
            loginHere: "Log in here",
            alreadyPublished: "You have already published a company.",
            viewProfile: "View my profile",
            alreadyPublishedMessage: "Your company is already published.",
            searchCommunePlaceholder: "Search commune...",
            searchProductPlaceholder: "Search product...",
            loading: "Loading...",
            imageRequired: "Please select an image"
        }
    };

    function createFilterableDropdown(options, placeholder, className, id, defaultText) {
        const dropdownHTML = `
            <div class="filterable-dropdown ${className}" data-dropdown-id="${id}">
                <div class="dropdown-selected" data-value="">
                    ${defaultText}
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

    function initDropdowns() {
        const dropdowns = document.querySelectorAll('.filterable-dropdown');
        
        dropdowns.forEach(dropdown => {
            const selected = dropdown.querySelector('.dropdown-selected');
            const options = dropdown.querySelector('.dropdown-options');
            const search = dropdown.querySelector('.dropdown-search');
            const allOptions = dropdown.querySelectorAll('.dropdown-option');
            
            selected.addEventListener('click', (e) => {
                e.stopPropagation();
                
                document.querySelectorAll('.dropdown-options').forEach(opt => opt.style.display = 'none');
                document.querySelectorAll('.input-group').forEach(group => group.classList.remove('dropdown-open'));
                
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

        publishSection.innerHTML = `
            <div class="publish-container">
                <h2 class="publish-title">${t.title}</h2>
                <div class="login-message">
                    ${t.loginRequired}
                    <br><br>
                    <a href="../log-in/log-in.html">${t.loginHere}</a>
                </div>
            </div>
        `;
    }

    function renderAlreadyPublished() {
        const lang = getLanguage();
        const t = translations[lang];

        publishSection.innerHTML = `
            <div class="publish-container">
                <h2 class="publish-title">${t.alreadyPublished}</h2>
                <div class="already-published-message">${t.alreadyPublishedMessage}</div>
                <div class="publish-actions">
                    <button id="viewProfileBtn" class="publish-button">${t.viewProfile}</button>
                </div>
            </div>
        `;

        document.getElementById('viewProfileBtn').addEventListener('click', () => {
            window.location.href = '../profile-view/profile-view.html';
        });
    }

    async function renderPublishForm() {
        const lang = getLanguage();
        const t = translations[lang];
        
        // Show loading state
        publishSection.innerHTML = `
            <div class="publish-container">
                <h2 class="publish-title">${t.title}</h2>
                <div class="login-message">${t.loading}</div>
            </div>
        `;
        
        try {
            // Fetch data
            const [products, communes] = await Promise.all([
                fetchProducts(),
                fetchCommunes()
            ]);
            
            console.log('Products loaded:', products);
            console.log('Communes loaded:', communes);
            
            if (!products || products.length === 0) {
                throw new Error('No products available');
            }
            
            if (!communes || communes.length === 0) {
                throw new Error('No communes available');
            }
            
            const productNames = products.map(p => lang === 'es' ? p.name_es : p.name_en);
            const communeNames = communes.map(c => c.name);

            const communeDropdown = createFilterableDropdown(
                communeNames, 
                t.searchCommunePlaceholder, 
                'commune-dropdown', 
                'commune',
                t.commune
            );
            
            const productDropdown = createFilterableDropdown(
                productNames, 
                t.searchProductPlaceholder, 
                'product-dropdown', 
                'product',
                t.productType
            );

            publishSection.innerHTML = `
                <div class="publish-container">
                    <h2 class="publish-title">${t.title}</h2>
                    <form id="publish-form" class="publish-form">
                        <div class="input-group">
                            <input type="text" id="companyName" class="publish-input" placeholder="${t.companyName}" required>
                        </div>
                        <div class="input-group">
                            <textarea id="productDescription" class="publish-textarea" placeholder="${t.productDescription}" required></textarea>
                        </div>
                        <div class="input-group">
                            <input type="text" id="address" class="publish-input" placeholder="${t.address}" required>
                        </div>
                        <div class="input-group">
                            <input type="tel" id="phone" class="publish-input" placeholder="${t.phone}" required>
                        </div>
                        <div class="input-group">
                            <input type="email" id="companyEmail" class="publish-input" placeholder="${t.companyEmail}" required>
                        </div>
                        <div class="input-group">
                            <div class="file-input-wrapper">
                                <input type="file" id="companyImage" class="file-input-hidden" accept="image/*" required>
                                <label for="companyImage" class="file-input-label" id="fileLabel">
                                    ${t.selectImage}
                                </label>
                            </div>
                        </div>                    
                        <div class="input-group">
                            ${communeDropdown}
                        </div>
                        <div class="input-group">
                            ${productDropdown}
                        </div>
                        <button type="submit" class="publish-button">${t.publishButton}</button>
                    </form>
                </div>
            `;

            initDropdowns();

            const form = document.getElementById("publish-form");
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
                
                const imageFile = document.getElementById("companyImage").files[0];
                if (!imageFile) {
                    alert(t.imageRequired);
                    return;
                }
                
                const submitButton = form.querySelector('.publish-button');
                const originalButtonText = submitButton.textContent;
                
                submitButton.disabled = true;
                submitButton.textContent = lang === 'es' ? 'Publicando...' : 'Publishing...';
                
                try {
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
                    
                    const description = document.getElementById("productDescription").value;
                    if (lang === 'es') {
                        formData.append('description_es', description);
                    } else {
                        formData.append('description_en', description);
                    }
                    
                    formData.append('image', imageFile);

                    const response = await apiRequest('/api/v1/companies/', {
                        method: 'POST',
                        body: formData
                    });

                    if (!response.ok) {
                        const errorData = await response.json().catch(() => ({}));
                        throw new Error(errorData.detail || 'Publish failed');
                    }
                    
                    const company = await response.json();
                    
                    console.log("Company published:", company);
                    
                    // Store company data and set publish state
                    setCompanyData(company);
                    setCompanyPublishState(true);
                    
                    alert(t.publishSuccess);
                    
                    // Redirect to profile view
                    window.location.href = '../profile-view/profile-view.html';
                    
                } catch (error) {
                    console.error('Error publishing company:', error);
                    alert(t.publishError + '\n' + error.message);
                } finally {
                    submitButton.disabled = false;
                    submitButton.textContent = originalButtonText;
                }
            });

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
            
        } catch (error) {
            console.error('Error loading form data:', error);
            publishSection.innerHTML = `
                <div class="publish-container">
                    <h2 class="publish-title">${t.title}</h2>
                    <div class="login-message" style="color: #ff6b6b;">
                        Error loading form data: ${error.message}
                        <br><br>
                        <button onclick="location.reload()" class="publish-button">Retry</button>
                    </div>
                </div>
            `;
        }
    }

    async function renderContent() {
        const isLoggedIn = getLoginState();
        const hasPublishedCompany = getCompanyPublishState();

        if (!isLoggedIn) {
            renderLoginRequired();
        } else if (hasPublishedCompany) {
            renderAlreadyPublished();
        } else {
            await renderPublishForm();
        }
    }

    document.addEventListener("languageChange", renderContent);
    document.addEventListener("userHasLogged", renderContent);
    document.addEventListener("companyPublishStateChange", renderContent);
    renderContent();
});
import { 
    getLanguage, 
    setCompanyData,
    fetchProducts,
    fetchCommunes,
    apiRequest
} from '../../../0-shared-components/utils/shared-functions.js';
import { sanitizeText, sanitizeURL, sanitizeEmail, sanitizePhone } from '../../../0-shared-components/utils/sanitizer.js';

document.addEventListener('DOMContentLoaded', () => {
    const profileEditSection = document.getElementById('profile-edit-section');

    const translations = {
        // ... (same translations as original)
    };

    async function fetchMyCompany() {
        try {
            const response = await apiRequest('/api/v1/companies/user/my-company');
            
            if (response.ok) {
                const company = await response.json();
                return company;
            } else if (response.status === 404) {
                return null;
            } else {
                throw new Error('Failed to fetch company');
            }
        } catch (error) {
            console.error('Error fetching company:', error);
            return null;
        }
    }

    function createFilterableDropdown(options, placeholder, className, id, defaultText, currentValue) {
        const dropdown = document.createElement('div');
        dropdown.className = `filterable-dropdown ${className}`;
        dropdown.setAttribute('data-dropdown-id', id);
        
        const safeCurrentValue = sanitizeText(currentValue || ''); // SAFE
        const safeSelectedText = sanitizeText(currentValue || defaultText); // SAFE
        
        const selected = document.createElement('div');
        selected.className = 'dropdown-selected';
        selected.setAttribute('data-value', safeCurrentValue);
        selected.textContent = safeSelectedText;
        
        const arrow = document.createElement('span');
        arrow.className = 'dropdown-arrow';
        arrow.textContent = '▼';
        selected.appendChild(arrow);
        
        const optionsContainer = document.createElement('div');
        optionsContainer.className = 'dropdown-options';
        optionsContainer.style.display = 'none';
        
        const searchInput = document.createElement('input');
        searchInput.type = 'text';
        searchInput.className = 'dropdown-search';
        searchInput.placeholder = placeholder;
        searchInput.autocomplete = 'off';
        
        const optionsList = document.createElement('div');
        optionsList.className = 'options-list';
        
        // SAFE: Sanitize all options
        options.forEach(option => {
            const optionDiv = document.createElement('div');
            optionDiv.className = 'dropdown-option';
            const safeOption = sanitizeText(option);
            optionDiv.setAttribute('data-value', safeOption);
            optionDiv.textContent = safeOption;
            optionsList.appendChild(optionDiv);
        });
        
        optionsContainer.appendChild(searchInput);
        optionsContainer.appendChild(optionsList);
        dropdown.appendChild(selected);
        dropdown.appendChild(optionsContainer);
        
        return dropdown;
    }

    function initDropdowns() {
        // ... (same initialization logic, no changes needed)
    }

    function renderLoginRequired() {
        // ... (same as original, uses textContent)
    }

    function renderNoCompany() {
        // ... (same as original, uses textContent)
    }

    async function renderEditForm() {
        const lang = getLanguage();
        const t = translations[lang];
        
        profileEditSection.textContent = '';
        
        const loadingContainer = document.createElement('div');
        loadingContainer.className = 'profile-edit-container';
        const title = document.createElement('h2');
        title.className = 'profile-edit-title';
        title.textContent = t.title;
        const message = document.createElement('div');
        message.className = 'login-message';
        message.textContent = t.loading;
        loadingContainer.appendChild(title);
        loadingContainer.appendChild(message);
        profileEditSection.appendChild(loadingContainer);
        
        const companyData = await fetchMyCompany();
        
        if (!companyData) {
            setCompanyPublishState(false);
            renderNoCompany();
            return;
        }
        
        const products = await fetchProducts();
        const communes = await fetchCommunes();
        
        const currentProduct = products.find(p => p.uuid === companyData.product_uuid);
        const currentCommune = communes.find(c => c.uuid === companyData.commune_uuid);
        
        const productNames = products.map(p => sanitizeText(lang === 'es' ? p.name_es : p.name_en)); // SAFE
        const communeNames = communes.map(c => sanitizeText(c.name)); // SAFE
        
        const currentProductName = currentProduct ? sanitizeText(lang === 'es' ? currentProduct.name_es : currentProduct.name_en) : null;
        const currentCommuneName = currentCommune ? sanitizeText(currentCommune.name) : null;

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

        profileEditSection.textContent = '';
        
        const container = document.createElement('div');
        container.className = 'profile-edit-container';
        
        const titleEl = document.createElement('h2');
        titleEl.className = 'profile-edit-title';
        titleEl.textContent = t.title;
        container.appendChild(titleEl);
        
        const form = document.createElement('form');
        form.id = 'profile-edit-form';
        form.className = 'profile-edit-form';
        
        // Company Name (SANITIZED)
        const nameGroup = document.createElement('div');
        nameGroup.className = 'input-group';
        const nameInput = document.createElement('input');
        nameInput.type = 'text';
        nameInput.id = 'companyName';
        nameInput.className = 'profile-edit-input';
        nameInput.placeholder = t.companyName;
        nameInput.value = sanitizeText(companyData.name || ''); // SAFE
        nameInput.required = true;
        nameGroup.appendChild(nameInput);
        form.appendChild(nameGroup);
        
        // Description (SANITIZED)
        const descGroup = document.createElement('div');
        descGroup.className = 'input-group';
        const descTextarea = document.createElement('textarea');
        descTextarea.id = 'productDescription';
        descTextarea.className = 'profile-edit-textarea';
        descTextarea.placeholder = t.productDescription;
        descTextarea.value = sanitizeText(lang === 'es' ? (companyData.description_es || '') : (companyData.description_en || '')); // SAFE
        descTextarea.required = true;
        descGroup.appendChild(descTextarea);
        form.appendChild(descGroup);
        
        // Address (SANITIZED)
        const addressGroup = document.createElement('div');
        addressGroup.className = 'input-group';
        const addressInput = document.createElement('input');
        addressInput.type = 'text';
        addressInput.id = 'address';
        addressInput.className = 'profile-edit-input';
        addressInput.placeholder = t.address;
        addressInput.value = sanitizeText(companyData.address || ''); // SAFE
        addressInput.required = true;
        addressGroup.appendChild(addressInput);
        form.appendChild(addressGroup);
        
        // Phone (SANITIZED)
        const phoneGroup = document.createElement('div');
        phoneGroup.className = 'input-group';
        const phoneInput = document.createElement('input');
        phoneInput.type = 'tel';
        phoneInput.id = 'phone';
        phoneInput.className = 'profile-edit-input';
        phoneInput.placeholder = t.phone;
        phoneInput.value = sanitizePhone(companyData.phone || ''); // SAFE
        phoneInput.required = true;
        phoneGroup.appendChild(phoneInput);
        form.appendChild(phoneGroup);
        
        // Email (SANITIZED)
        const emailGroup = document.createElement('div');
        emailGroup.className = 'input-group';
        const emailInput = document.createElement('input');
        emailInput.type = 'email';
        emailInput.id = 'companyEmail';
        emailInput.className = 'profile-edit-input';
        emailInput.placeholder = t.companyEmail;
        emailInput.value = sanitizeEmail(companyData.email || ''); // SAFE
        emailInput.required = true;
        emailGroup.appendChild(emailInput);
        form.appendChild(emailGroup);
        
        // Commune dropdown
        const communeGroup = document.createElement('div');
        communeGroup.className = 'input-group';
        communeGroup.appendChild(communeDropdown);
        form.appendChild(communeGroup);
        
        // Product dropdown
        const productGroup = document.createElement('div');
        productGroup.className = 'input-group';
        productGroup.appendChild(productDropdown);
        form.appendChild(productGroup);
        
        // Current image display (SANITIZED URL)
        const imageGroup = document.createElement('div');
        imageGroup.className = 'input-group';
        
        const currentImageContainer = document.createElement('div');
        currentImageContainer.className = 'current-image-container';
        
        const imageLabel = document.createElement('label');
        imageLabel.className = 'current-image-label';
        imageLabel.textContent = t.currentImage;
        currentImageContainer.appendChild(imageLabel);
        
        if (companyData.image_url) {
            const img = document.createElement('img');
            img.src = sanitizeURL(companyData.image_url); // SAFE
            img.alt = 'Company Image';
            img.className = 'current-image';
            currentImageContainer.appendChild(img);
        } else {
            const noImage = document.createElement('div');
            noImage.className = 'no-image-placeholder';
            noImage.textContent = t.noImage;
            currentImageContainer.appendChild(noImage);
        }
        
        const fileWrapper = document.createElement('div');
        fileWrapper.className = 'file-input-wrapper';
        
        const fileInput = document.createElement('input');
        fileInput.type = 'file';
        fileInput.id = 'companyImage';
        fileInput.className = 'file-input-hidden';
        fileInput.accept = 'image/*';
        
        const fileLabel = document.createElement('label');
        fileLabel.htmlFor = 'companyImage';
        fileLabel.className = 'file-input-label';
        fileLabel.id = 'fileLabel';
        fileLabel.textContent = t.selectImage;
        
        fileWrapper.appendChild(fileInput);
        fileWrapper.appendChild(fileLabel);
        
        imageGroup.appendChild(currentImageContainer);
        imageGroup.appendChild(fileWrapper);
        form.appendChild(imageGroup);
        
        // Action buttons
        const actionsGroup = document.createElement('div');
        actionsGroup.className = 'profile-edit-actions';
        
        const submitBtn = document.createElement('button');
        submitBtn.type = 'submit';
        submitBtn.className = 'profile-edit-button';
        submitBtn.textContent = t.updateButton;
        
        const cancelBtn = document.createElement('button');
        cancelBtn.type = 'button';
        cancelBtn.id = 'cancelBtn';
        cancelBtn.className = 'profile-edit-button secondary';
        cancelBtn.textContent = t.cancelButton;
        
        const deleteBtn = document.createElement('button');
        deleteBtn.type = 'button';
        deleteBtn.id = 'deleteBtn';
        deleteBtn.className = 'profile-edit-button danger';
        deleteBtn.textContent = t.deleteButton;
        
        actionsGroup.appendChild(submitBtn);
        actionsGroup.appendChild(cancelBtn);
        actionsGroup.appendChild(deleteBtn);
        form.appendChild(actionsGroup);
        
        container.appendChild(form);
        profileEditSection.appendChild(container);

        initDropdowns();
        
        const companyUUID = companyData.uuid;

        // Form submit handler
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

            submitBtn.disabled = true;
            const originalText = submitBtn.textContent;
            submitBtn.textContent = t.updating;

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
                setCompanyData(updatedCompany);
                showMessage(t.updateSuccess, 'success');

                setTimeout(() => {
                    renderEditForm();
                }, 2000);

            } catch (error) {
                console.error('Error updating company:', error);
                showMessage(t.updateError + '\n' + error.message, 'error');
            } finally {
                submitBtn.disabled = false;
                submitBtn.textContent = originalText;
            }
        });

        // Cancel button
        cancelBtn.addEventListener('click', () => {
            window.location.href = '../profile-view/profile-view.html';
        });

        // Delete button
        deleteBtn.addEventListener('click', async () => {
            // ... (same delete logic as original)
        });

        // File input handling
        fileInput.addEventListener("change", (e) => {
            const fileName = e.target.files[0]?.name;
            
            if (fileName) {
                fileLabel.textContent = `✅ ${sanitizeText(fileName)}`; // SAFE
                fileLabel.classList.add("has-file");
            } else {
                fileLabel.textContent = t.selectImage;
                fileLabel.classList.remove("has-file");
            }
        });
    }

    function showMessage(message, type) {
        // ... (same as original, uses textContent)
    }

    async function renderContent() {
        // ... (same as original)
    }

    document.addEventListener("languageChange", renderContent);
    document.addEventListener("userHasLogged", renderContent);
    document.addEventListener("companyPublishStateChange", renderContent);
    document.addEventListener("companyDataChange", renderContent);
    
    renderContent();
});
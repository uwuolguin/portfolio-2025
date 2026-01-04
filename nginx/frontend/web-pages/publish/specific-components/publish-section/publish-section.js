import {
    getLanguage,
    apiRequest,
    fetchProducts,
    fetchCommunes
} from '../../../0-shared-components/utils/shared-functions.js';

//  ADDED: Import all necessary sanitizer functions
import {
    sanitizeText,
    sanitizeEmail,
    sanitizePhone,
    sanitizeAPIResponse,
    validateFormData,
    buildDropdownOption
} from '../../../0-shared-components/utils/sanitizer.js';

document.addEventListener('DOMContentLoaded', async () => {
    const publishSection = document.getElementById('publish-section');

    const translations = {
        es: {
            title: 'Publicar Mi Empresa',
            companyName: 'Nombre de la Empresa',
            email: 'Correo de Contacto',
            phone: 'Teléfono',
            address: 'Dirección',
            commune: 'Comuna',
            product: 'Producto/Servicio',
            description: 'Descripción',
            image: 'Imagen de la Empresa',
            selectImage: 'Seleccionar imagen...',
            publish: 'Publicar',
            cancel: 'Cancelar',
            selectCommune: 'Seleccionar Comuna',
            selectProduct: 'Seleccionar Producto',
            loading: 'Cargando...',
            publishing: 'Publicando...',
            success: '¡Empresa publicada exitosamente!',
            error: 'Error al publicar la empresa',
            alreadyPublished: 'Ya tienes una empresa publicada',
            viewCompany: 'Ver Mi Empresa',
            loginRequired: 'Debes iniciar sesión para publicar',
            loginHere: 'Iniciar sesión',
            searchPlaceholder: 'Buscar...'
        },
        en: {
            title: 'Publish My Company',
            companyName: 'Company Name',
            email: 'Contact Email',
            phone: 'Phone',
            address: 'Address',
            commune: 'Commune',
            product: 'Product/Service',
            description: 'Description',
            image: 'Company Image',
            selectImage: 'Select image...',
            publish: 'Publish',
            cancel: 'Cancel',
            selectCommune: 'Select Commune',
            selectProduct: 'Select Product',
            loading: 'Loading...',
            publishing: 'Publishing...',
            success: 'Company published successfully!',
            error: 'Error publishing company',
            alreadyPublished: 'You already have a published company',
            viewCompany: 'View My Company',
            loginRequired: 'You must log in to publish',
            loginHere: 'Log in',
            searchPlaceholder: 'Search...'
        }
    };

    async function checkExistingCompany() {
        try {
            const response = await apiRequest('/api/v1/companies/user/my-company');
            if (response.ok) {
                return true;
            }
            return false;
        } catch (error) {
            return false;
        }
    }

    function createFilterableDropdown(id, label, options, placeholder) {
        const container = document.createElement('div');
        container.className = 'input-group';
        container.dataset.dropdownId = id;

        const selected = document.createElement('div');
        selected.className = 'dropdown-selected';
        selected.dataset.value = '';
        
        const selectedText = document.createElement('span');
        selectedText.textContent = placeholder;
        selected.appendChild(selectedText);
        
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
        searchInput.placeholder = translations[getLanguage()].searchPlaceholder;
        optionsContainer.appendChild(searchInput);

        const optionsList = document.createElement('div');
        optionsList.className = 'options-list';

        //  Data already sanitized from fetchProducts/fetchCommunes
        options.forEach(option => {
            const optionElement = buildDropdownOption(
                option.uuid || option.name,
                option.name_es || option.name_en || option.name
            );
            
            optionElement.addEventListener('click', () => {
                selectedText.textContent = option.name_es || option.name_en || option.name;
                selected.dataset.value = option.uuid || option.name;
                optionsContainer.style.display = 'none';
                container.classList.remove('dropdown-open');
            });
            
            optionsList.appendChild(optionElement);
        });

        optionsContainer.appendChild(optionsList);

        // Search functionality
        searchInput.addEventListener('input', (e) => {
            const searchTerm = sanitizeText(e.target.value.toLowerCase());
            const allOptions = optionsList.querySelectorAll('.dropdown-option');
            
            allOptions.forEach(opt => {
                const text = opt.textContent.toLowerCase();
                opt.style.display = text.includes(searchTerm) ? 'block' : 'none';
            });
        });

        // Toggle dropdown
        selected.addEventListener('click', (e) => {
            e.stopPropagation();
            const isOpen = optionsContainer.style.display === 'block';
            
            // Close all other dropdowns
            document.querySelectorAll('.dropdown-options').forEach(opt => {
                opt.style.display = 'none';
            });
            document.querySelectorAll('.input-group').forEach(grp => {
                grp.classList.remove('dropdown-open');
            });
            
            if (!isOpen) {
                optionsContainer.style.display = 'block';
                container.classList.add('dropdown-open');
                searchInput.value = '';
                searchInput.focus();
                
                // Reset all options visibility
                optionsList.querySelectorAll('.dropdown-option').forEach(opt => {
                    opt.style.display = 'block';
                });
            }
        });

        // Close dropdown when clicking outside
        document.addEventListener('click', () => {
            optionsContainer.style.display = 'none';
            container.classList.remove('dropdown-open');
        });

        container.appendChild(selected);
        container.appendChild(optionsContainer);

        return container;
    }

    async function renderPublishForm() {
        const lang = getLanguage();
        const t = translations[lang];

        publishSection.innerHTML = `<div class="loading" style="color: white; text-align: center; padding: 2rem;">${t.loading}</div>`;

        // Check if user already has a company
        const hasCompany = await checkExistingCompany();
        if (hasCompany) {
            publishSection.innerHTML = '';
            
            const container = document.createElement('div');
            container.className = 'publish-container';
            
            const message = document.createElement('p');
            message.className = 'already-published-message';
            message.textContent = t.alreadyPublished;
            
            const viewButton = document.createElement('button');
            viewButton.className = 'publish-button';
            viewButton.textContent = t.viewCompany;
            viewButton.addEventListener('click', () => {
                window.location.href = '/profile-view/profile-view.html';
            });
            
            container.appendChild(message);
            container.appendChild(viewButton);
            publishSection.appendChild(container);
            return;
        }

        //  CRITICAL FIX: Sanitize API responses
        const rawProducts = await fetchProducts();
        const rawCommunes = await fetchCommunes();
        const products = sanitizeAPIResponse(rawProducts);
        const communes = sanitizeAPIResponse(rawCommunes);

        publishSection.innerHTML = '';

        const container = document.createElement('div');
        container.className = 'publish-container';

        const title = document.createElement('h2');
        title.className = 'publish-title';
        title.textContent = t.title;
        container.appendChild(title);

        const form = document.createElement('form');
        form.className = 'publish-form';
        form.id = 'publish-form';

        // Company name
        const nameGroup = document.createElement('div');
        nameGroup.className = 'input-group';
        const nameInput = document.createElement('input');
        nameInput.type = 'text';
        nameInput.name = 'name';
        nameInput.className = 'publish-input';
        nameInput.placeholder = t.companyName;
        nameInput.required = true;
        nameGroup.appendChild(nameInput);
        form.appendChild(nameGroup);

        // Email
        const emailGroup = document.createElement('div');
        emailGroup.className = 'input-group';
        const emailInput = document.createElement('input');
        emailInput.type = 'email';
        emailInput.name = 'email';
        emailInput.className = 'publish-input';
        emailInput.placeholder = t.email;
        emailInput.required = true;
        emailGroup.appendChild(emailInput);
        form.appendChild(emailGroup);

        // Phone
        const phoneGroup = document.createElement('div');
        phoneGroup.className = 'input-group';
        const phoneInput = document.createElement('input');
        phoneInput.type = 'tel';
        phoneInput.name = 'phone';
        phoneInput.className = 'publish-input';
        phoneInput.placeholder = t.phone;
        phoneInput.required = true;
        phoneGroup.appendChild(phoneInput);
        form.appendChild(phoneGroup);

        // Address
        const addressGroup = document.createElement('div');
        addressGroup.className = 'input-group';
        const addressInput = document.createElement('input');
        addressInput.type = 'text';
        addressInput.name = 'address';
        addressInput.className = 'publish-input';
        addressInput.placeholder = t.address;
        addressInput.required = true;
        addressGroup.appendChild(addressInput);
        form.appendChild(addressGroup);

        // Commune dropdown
        const communeDropdown = createFilterableDropdown(
            'commune',
            t.commune,
            communes,
            t.selectCommune
        );
        form.appendChild(communeDropdown);

        // Product dropdown
        const productDropdown = createFilterableDropdown(
            'product',
            t.product,
            products,
            t.selectProduct
        );
        form.appendChild(productDropdown);

        // Description
        const descGroup = document.createElement('div');
        descGroup.className = 'input-group';
        const descTextarea = document.createElement('textarea');
        descTextarea.name = 'description';
        descTextarea.className = 'publish-textarea';
        descTextarea.placeholder = t.description;
        descTextarea.rows = 4;
        descGroup.appendChild(descTextarea);
        form.appendChild(descGroup);

        // Image upload
        const imageGroup = document.createElement('div');
        imageGroup.className = 'input-group';
        
        const fileWrapper = document.createElement('div');
        fileWrapper.className = 'file-input-wrapper';
        
        const fileInput = document.createElement('input');
        fileInput.type = 'file';
        fileInput.id = 'company-image';
        fileInput.name = 'image';
        fileInput.className = 'file-input-hidden';
        fileInput.accept = 'image/jpeg,image/png';
        fileInput.required = true;
        
        const fileLabel = document.createElement('label');
        fileLabel.htmlFor = 'company-image';
        fileLabel.className = 'file-input-label';
        fileLabel.textContent = t.selectImage;
        
        fileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                fileLabel.textContent = sanitizeText(e.target.files[0].name);
                fileLabel.classList.add('has-file');
            } else {
                fileLabel.textContent = t.selectImage;
                fileLabel.classList.remove('has-file');
            }
        });
        
        fileWrapper.appendChild(fileInput);
        fileWrapper.appendChild(fileLabel);
        imageGroup.appendChild(fileWrapper);
        form.appendChild(imageGroup);

        // Error message container
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-message';
        errorDiv.style.display = 'none';
        errorDiv.style.color = '#ff6b6b';
        errorDiv.style.marginBottom = '1rem';
        form.appendChild(errorDiv);

        // Success message container
        const successDiv = document.createElement('div');
        successDiv.className = 'success-message';
        successDiv.style.display = 'none';
        successDiv.style.color = '#4CAF50';
        successDiv.style.marginBottom = '1rem';
        form.appendChild(successDiv);

        // Buttons
        const buttonGroup = document.createElement('div');
        buttonGroup.className = 'publish-actions';

        const publishButton = document.createElement('button');
        publishButton.type = 'submit';
        publishButton.className = 'publish-button';
        publishButton.textContent = t.publish;

        const cancelButton = document.createElement('button');
        cancelButton.type = 'button';
        cancelButton.className = 'publish-button secondary';
        cancelButton.textContent = t.cancel;
        cancelButton.addEventListener('click', () => {
            window.location.href = '/front-page/front-page.html';
        });

        buttonGroup.appendChild(publishButton);
        buttonGroup.appendChild(cancelButton);
        form.appendChild(buttonGroup);

        //  CRITICAL FIX: Validate, sanitize, and use apiRequest
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            errorDiv.style.display = 'none';
            successDiv.style.display = 'none';

            try {
                // Get selected values
                const communeSelected = communeDropdown.querySelector('.dropdown-selected');
                const productSelected = productDropdown.querySelector('.dropdown-selected');
                
                const communeValue = communeSelected.dataset.value;
                const productValue = productSelected.dataset.value;

                if (!communeValue) {
                    throw new Error(t.selectCommune);
                }
                if (!productValue) {
                    throw new Error(t.selectProduct);
                }

                //  Validate and sanitize form data
                const validatedData = validateFormData({
                    name: nameInput.value,
                    email: emailInput.value,
                    phone: phoneInput.value,
                    address: addressInput.value,
                    description: descTextarea.value
                });

                // Create FormData for multipart upload
                const formData = new FormData();
                formData.append('name', validatedData.name);
                formData.append('email', validatedData.email);
                formData.append('phone', validatedData.phone);
                formData.append('address', validatedData.address);
                formData.append('description_es', validatedData.description);
                formData.append('commune_name', sanitizeText(communeValue));
                formData.append('product_name', sanitizeText(productValue));
                formData.append('lang', lang);
                formData.append('image', fileInput.files[0]);

                publishButton.disabled = true;
                publishButton.textContent = t.publishing;

                //  CHANGED: Use apiRequest instead of fetch
                const response = await apiRequest('/api/v1/companies/', {
                    method: 'POST',
                    body: formData
                    // Note: Don't set Content-Type for FormData, browser handles it
                });

                if (response.ok) {
                    successDiv.textContent = t.success;
                    successDiv.style.display = 'block';
                    
                    setTimeout(() => {
                        window.location.href = '/profile-view/profile-view.html';
                    }, 2000);
                } else {
                    const error = await response.json();
                    throw new Error(error.detail || t.error);
                }

            } catch (error) {
                console.error('Publish error:', error);
                //  FIXED: Sanitize error message before display
                errorDiv.textContent = sanitizeText(error.message) || t.error;
                errorDiv.style.display = 'block';
                publishButton.disabled = false;
                publishButton.textContent = t.publish;
            }
        });

        container.appendChild(form);
        publishSection.appendChild(container);
    }

    await renderPublishForm();

    document.addEventListener('languageChange', renderPublishForm);
});
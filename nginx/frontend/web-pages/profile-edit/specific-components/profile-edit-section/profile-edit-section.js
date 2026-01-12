import {
    getLanguage,
    apiRequest,
    fetchProducts,
    fetchCommunes
} from '../../../0-shared-components/utils/shared-functions.js';

//  ADDED: Import all necessary sanitizer functions
import {
    sanitizeText,
    sanitizeAPIResponse,
    validateFormData,
    buildDropdownOption
} from '../../../0-shared-components/utils/sanitizer.js';

document.addEventListener('DOMContentLoaded', async () => {
    const editSection = document.getElementById('profile-edit-section');

    const translations = {
        es: {
            title: 'Editar Mi Empresa',
            companyName: 'Nombre de la Empresa',
            email: 'Correo de Contacto',
            phone: 'Teléfono',
            address: 'Dirección',
            commune: 'Comuna',
            product: 'Producto/Servicio',
            description: 'Descripción',
            image: 'Cambiar Imagen',
            selectImage: 'Seleccionar nueva imagen...',
            save: 'Guardar Cambios',
            cancel: 'Cancelar',
            delete: 'Eliminar Empresa',
            selectCommune: 'Seleccionar Comuna',
            selectProduct: 'Seleccionar Producto',
            loading: 'Cargando...',
            saving: 'Guardando...',
            success: '¡Cambios guardados exitosamente!',
            error: 'Error al guardar los cambios',
            deleteConfirm: '¿Estás seguro de que deseas eliminar tu empresa? Esta acción no se puede deshacer.',
            deleteSuccess: 'Empresa eliminada exitosamente',
            deleteError: 'Error al eliminar la empresa',
            searchPlaceholder: 'Buscar...'
        },
        en: {
            title: 'Edit My Company',
            companyName: 'Company Name',
            email: 'Contact Email',
            phone: 'Phone',
            address: 'Address',
            commune: 'Commune',
            product: 'Product/Service',
            description: 'Description',
            image: 'Change Image',
            selectImage: 'Select new image...',
            save: 'Save Changes',
            cancel: 'Cancel',
            delete: 'Delete Company',
            selectCommune: 'Select Commune',
            selectProduct: 'Select Product',
            loading: 'Loading...',
            saving: 'Saving...',
            success: 'Changes saved successfully!',
            error: 'Error saving changes',
            deleteConfirm: 'Are you sure you want to delete your company? This action cannot be undone.',
            deleteSuccess: 'Company deleted successfully',
            deleteError: 'Error deleting company',
            searchPlaceholder: 'Search...'
        }
    };

    let currentCompany = null;

    async function loadCurrentCompany() {
        try {
            const response = await apiRequest('/api/v1/companies/user/my-company');
            if (response.ok) {
                const data = await response.json();
                //  Sanitize API response
                currentCompany = sanitizeAPIResponse(data);
                return currentCompany;
            }
            throw new Error('Company not found');
        } catch (error) {
            console.error('Error loading company:', error);
            return null;
        }
    }

    function createFilterableDropdown(id, label, options, placeholder, selectedValue = null) {
        const container = document.createElement('div');
        container.className = 'input-group';
        container.dataset.dropdownId = id;

        const selected = document.createElement('div');
        selected.className = 'dropdown-selected';
        
        // Find the selected option
        const selectedOption = options.find(opt => 
            (opt.uuid || opt.name) === selectedValue || 
            (opt.name_es || opt.name_en || opt.name) === selectedValue
        );
        
        selected.dataset.value = selectedOption ? (selectedOption.uuid || selectedOption.name) : '';
        
        const selectedText = document.createElement('span');
        selectedText.textContent = selectedOption ? 
            (selectedOption.name_es || selectedOption.name_en || selectedOption.name) : 
            placeholder;
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

    async function renderEditForm() {
        const lang = getLanguage();
        const t = translations[lang];

        editSection.innerHTML = `<div class="loading" style="color: white; text-align: center; padding: 2rem;">${t.loading}</div>`;

        const company = await loadCurrentCompany();
        if (!company) {
            editSection.innerHTML = '<p style="color: white; text-align: center;">Error loading company data</p>';
            return;
        }

        //  CRITICAL FIX: Sanitize API responses
        const rawProducts = await fetchProducts();
        const rawCommunes = await fetchCommunes();
        const products = sanitizeAPIResponse(rawProducts);
        const communes = sanitizeAPIResponse(rawCommunes);

        editSection.innerHTML = '';

        const container = document.createElement('div');
        container.className = 'profile-edit-container';

        const title = document.createElement('h2');
        title.className = 'profile-edit-title';
        title.textContent = t.title;
        container.appendChild(title);

        const form = document.createElement('form');
        form.className = 'profile-edit-form';
        form.id = 'profile-edit-form';

        // Company name
        const nameGroup = document.createElement('div');
        nameGroup.className = 'input-group';
        const nameInput = document.createElement('input');
        nameInput.type = 'text';
        nameInput.name = 'name';
        nameInput.className = 'profile-edit-input';
        nameInput.placeholder = t.companyName;
        nameInput.value = company.name || '';
        nameInput.required = true;
        nameGroup.appendChild(nameInput);
        form.appendChild(nameGroup);

        // Email
        const emailGroup = document.createElement('div');
        emailGroup.className = 'input-group';
        const emailInput = document.createElement('input');
        emailInput.type = 'email';
        emailInput.name = 'email';
        emailInput.className = 'profile-edit-input';
        emailInput.placeholder = t.email;
        emailInput.value = company.email || '';
        emailInput.required = true;
        emailGroup.appendChild(emailInput);
        form.appendChild(emailGroup);

        // Phone
        const phoneGroup = document.createElement('div');
        phoneGroup.className = 'input-group';
        const phoneInput = document.createElement('input');
        phoneInput.type = 'tel';
        phoneInput.name = 'phone';
        phoneInput.className = 'profile-edit-input';
        phoneInput.placeholder = t.phone;
        phoneInput.value = company.phone || '';
        phoneInput.required = true;
        phoneGroup.appendChild(phoneInput);
        form.appendChild(phoneGroup);

        // Address
        const addressGroup = document.createElement('div');
        addressGroup.className = 'input-group';
        const addressInput = document.createElement('input');
        addressInput.type = 'text';
        addressInput.name = 'address';
        addressInput.className = 'profile-edit-input';
        addressInput.placeholder = t.address;
        addressInput.value = company.address || '';
        addressInput.required = true;
        addressGroup.appendChild(addressInput);
        form.appendChild(addressGroup);

        // Commune dropdown
        const communeDropdown = createFilterableDropdown(
            'commune',
            t.commune,
            communes,
            t.selectCommune,
            company.commune
        );
        form.appendChild(communeDropdown);

        // Product dropdown
        const productDropdown = createFilterableDropdown(
            'product',
            t.product,
            products,
            t.selectProduct,
            company.product
        );
        form.appendChild(productDropdown);

        // Description
        const descGroup = document.createElement('div');
        descGroup.className = 'input-group';
        const descTextarea = document.createElement('textarea');
        descTextarea.name = 'description';
        descTextarea.className = 'profile-edit-textarea';
        descTextarea.placeholder = t.description;
        descTextarea.rows = 4;
        descTextarea.value = (lang === 'es' ? company.description_es : company.description_en) || '';
        descGroup.appendChild(descTextarea);
        form.appendChild(descGroup);

        // Current image preview
        if (company.image_url) {
            const currentImageDiv = document.createElement('div');
            currentImageDiv.className = 'current-image-preview';
            
            const previewLabel = document.createElement('p');
            previewLabel.textContent = 'Imagen actual:';
            previewLabel.style.color = 'white';
            currentImageDiv.appendChild(previewLabel);
            
            const imgPreview = document.createElement('img');
            imgPreview.src = company.image_url;
            imgPreview.alt = 'Current company image';
            imgPreview.style.maxWidth = '200px';
            imgPreview.style.borderRadius = '8px';
            currentImageDiv.appendChild(imgPreview);
            
            form.appendChild(currentImageDiv);
        }

        // Image upload (optional for edit)
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
        buttonGroup.className = 'profile-edit-actions';

        const saveButton = document.createElement('button');
        saveButton.type = 'submit';
        saveButton.className = 'profile-edit-button';
        saveButton.textContent = t.save;

        const cancelButton = document.createElement('button');
        cancelButton.type = 'button';
        cancelButton.className = 'profile-edit-button secondary';
        cancelButton.textContent = t.cancel;
        cancelButton.addEventListener('click', () => {
            window.location.href = '/profile-view/profile-view.html';
        });

        const deleteButton = document.createElement('button');
        deleteButton.type = 'button';
        deleteButton.className = 'profile-edit-button danger';
        deleteButton.textContent = t.delete;
        deleteButton.addEventListener('click', async () => {
            if (confirm(t.deleteConfirm)) {
                try {
                    const response = await apiRequest(`/api/v1/companies/user/my-company`, {
                        method: 'DELETE'
                    });

                    if (response.ok) {
                        //  FIXED: Use safe alert with sanitized message
                        window.alert(t.deleteSuccess);
                        window.location.href = '/front-page/front-page.html';
                    } else {
                        throw new Error(t.deleteError);
                    }
                } catch (error) {
                    console.error('Delete error:', error);
                    //  FIXED: Sanitize error message
                    window.alert(sanitizeText(error.message) || t.deleteError);
                }
            }
        });

        buttonGroup.appendChild(saveButton);
        buttonGroup.appendChild(cancelButton);
        buttonGroup.appendChild(deleteButton);
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
                
                // Only append image if a new one was selected
                if (fileInput.files.length > 0) {
                    formData.append('image', fileInput.files[0]);
                }

                saveButton.disabled = true;
                saveButton.textContent = t.saving;

                //  CHANGED: Use apiRequest instead of fetch
                const response = await apiRequest(`/api/v1/companies/user/my-company`, {
                    method: 'PATCH',
                    body: formData
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
                console.error('Save error:', error);
                //  FIXED: Sanitize error message before display
                errorDiv.textContent = sanitizeText(error.message) || t.error;
                errorDiv.style.display = 'block';
                saveButton.disabled = false;
                saveButton.textContent = t.save;
            }
        });

        container.appendChild(form);
        editSection.appendChild(container);
    }

    await renderEditForm();

    document.addEventListener('stateChange', renderEditForm);
});
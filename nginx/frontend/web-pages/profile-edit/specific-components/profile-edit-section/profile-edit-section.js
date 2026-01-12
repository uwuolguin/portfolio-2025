let initialized = false;  // Guard flag

document.addEventListener('DOMContentLoaded', async () => {
    if (initialized) return; // Prevent re-initialization
    initialized = true; // Set the guard flag after first initialization

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

        const normalize = v => sanitizeText(String(v || '').toLowerCase());

        // text-only match
        const selectedOption = options.find(opt =>
            normalize(opt.name) === normalize(selectedValue) ||
            normalize(opt.name_es) === normalize(selectedValue) ||
            normalize(opt.name_en) === normalize(selectedValue)
        );

        const canonicalValue = selectedOption?.name || '';

        selected.dataset.value = canonicalValue;

        const selectedText = document.createElement('span');
        selectedText.textContent = selectedOption
            ? (optLabel(selectedOption))
            : placeholder;
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

        options.forEach(option => {
            const label = optLabel(option);
            const optionElement = buildDropdownOption(label, label);

            optionElement.addEventListener('click', () => {
                selectedText.textContent = label;
                selected.dataset.value = option.name;
                optionsContainer.style.display = 'none';
                container.classList.remove('dropdown-open');
            });

            optionsList.appendChild(optionElement);
        });

        optionsContainer.appendChild(optionsList);

        searchInput.addEventListener('input', e => {
            const term = normalize(e.target.value);
            optionsList.querySelectorAll('.dropdown-option').forEach(opt => {
                opt.style.display = normalize(opt.textContent).includes(term)
                    ? 'block'
                    : 'none';
            });
        });

        selected.addEventListener('click', e => {
            e.stopPropagation();

            document.querySelectorAll('.dropdown-options').forEach(o => o.style.display = 'none');
            document.querySelectorAll('.input-group').forEach(g => g.classList.remove('dropdown-open'));

            optionsContainer.style.display = 'block';
            container.classList.add('dropdown-open');
            searchInput.value = '';
            searchInput.focus();

            optionsList.querySelectorAll('.dropdown-option').forEach(opt => {
                opt.style.display = 'block';
            });
        });

        document.addEventListener('click', () => {
            optionsContainer.style.display = 'none';
            container.classList.remove('dropdown-open');
        });

        container.appendChild(selected);
        container.appendChild(optionsContainer);
        return container;
    }

    function optLabel(option) {
        const lang = getLanguage();
        return sanitizeText(
            lang === 'es'
                ? option.name_es || option.name
                : option.name_en || option.name
        );
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

        fileWrapper.appendChild(fileInput);
        imageGroup.appendChild(fileWrapper);
        form.appendChild(imageGroup);

        container.appendChild(form);
        editSection.appendChild(container);
    }

    await renderEditForm();
});

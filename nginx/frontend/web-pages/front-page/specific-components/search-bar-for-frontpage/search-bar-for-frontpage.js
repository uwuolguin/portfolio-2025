import {
    getLanguage,
    fetchProducts,
    fetchCommunes,
    debounce
} from '../../../0-shared-components/utils/shared-functions.js';

import {
    sanitizeAPIResponse,
    buildDropdownOption,
    clearElement
} from '../../../0-shared-components/utils/sanitizer.js';

document.addEventListener('DOMContentLoaded', async () => {
    const searchContainer = document.getElementById('search-container');

    const translations = {
        es: {
            placeholder: 'Buscar empresas...',
            searchButton: 'Buscar',
            commune: 'Comuna',
            product: 'Producto',
            allCommunes: 'Todas Las Comunas',
            allProducts: 'Todos Los Productos',
            searchPlaceholder: 'Buscar...'
        },
        en: {
            placeholder: 'Search companies...',
            searchButton: 'Search',
            commune: 'Commune',
            product: 'Product',
            allCommunes: 'All Communes',
            allProducts: 'All Products',
            searchPlaceholder: 'Search...'
        }
    };

    function createFilterableDropdown(id, options, defaultText, searchPlaceholder) {
        const container = document.createElement('div');
        container.className = 'filterable-dropdown';
        container.dataset.dropdownId = id;

        // Selected display
        const selected = document.createElement('div');
        selected.className = 'dropdown-selected';
        selected.dataset.value = '';
        
        const selectedText = document.createElement('span');
        selectedText.textContent = defaultText;
        selected.appendChild(selectedText);
        
        const arrow = document.createElement('span');
        arrow.className = 'dropdown-arrow';
        arrow.textContent = '▼';
        selected.appendChild(arrow);

        // Options container
        const optionsContainer = document.createElement('div');
        optionsContainer.className = 'dropdown-options';
        optionsContainer.style.display = 'none';

        // Search input
        const searchInput = document.createElement('input');
        searchInput.type = 'text';
        searchInput.className = 'dropdown-search';
        searchInput.placeholder = searchPlaceholder;
        optionsContainer.appendChild(searchInput);

        // Options list
        const optionsList = document.createElement('div');
        optionsList.className = 'options-list';

        // Default "All" option
        const defaultOption = buildDropdownOption('', defaultText);
        defaultOption.addEventListener('click', () => {
            selectedText.textContent = defaultText;
            selected.dataset.value = '';
            optionsContainer.style.display = 'none';
            // Trigger search input changed event
            document.dispatchEvent(new CustomEvent('searchInputChanged'));
        });
        optionsList.appendChild(defaultOption);

        // Add options (data already sanitized)
        const lang = getLanguage();
        options.forEach(option => {
            const displayName = lang === 'es' 
                ? (option.name_es || option.name_en || option.name || '')
                : (option.name_en || option.name_es || option.name || '');
            const value = option.name_es || option.name_en || option.name || option.uuid || '';
            
            const optionElement = buildDropdownOption(value, displayName);
            
            optionElement.addEventListener('click', () => {
                selectedText.textContent = displayName;
                selected.dataset.value = value;
                optionsContainer.style.display = 'none';
                // Trigger search input changed event
                document.dispatchEvent(new CustomEvent('searchInputChanged'));
            });
            
            optionsList.appendChild(optionElement);
        });

        optionsContainer.appendChild(optionsList);

        // Search filter functionality
        searchInput.addEventListener('input', (e) => {
            const searchTerm = e.target.value.toLowerCase();
            const allOptions = optionsList.querySelectorAll('.dropdown-option');
            
            allOptions.forEach(opt => {
                const text = opt.textContent.toLowerCase();
                opt.style.display = text.includes(searchTerm) ? 'block' : 'none';
            });
        });

        // Prevent search input clicks from closing dropdown
        searchInput.addEventListener('click', (e) => {
            e.stopPropagation();
        });

        // Toggle dropdown
        selected.addEventListener('click', (e) => {
            e.stopPropagation();
            const isOpen = optionsContainer.style.display === 'block';
            
            // Close all other dropdowns first
            document.querySelectorAll('.dropdown-options').forEach(opt => {
                opt.style.display = 'none';
            });
            
            if (!isOpen) {
                optionsContainer.style.display = 'block';
                searchInput.value = '';
                searchInput.focus();
                // Reset all options visibility
                optionsList.querySelectorAll('.dropdown-option').forEach(opt => {
                    opt.style.display = 'block';
                });
            }
        });

        container.appendChild(selected);
        container.appendChild(optionsContainer);

        return container;
    }

    async function renderSearchBar() {
        const lang = getLanguage();
        const t = translations[lang];

        // Fetch and sanitize data
        const rawProducts = await fetchProducts();
        const rawCommunes = await fetchCommunes();
        
        const products = sanitizeAPIResponse(rawProducts);
        const communes = sanitizeAPIResponse(rawCommunes);

        // Clear container safely
        clearElement(searchContainer);

        // Create search bar wrapper
        const searchWrapper = document.createElement('div');
        searchWrapper.className = 'search-flex-container';

        // Search input container
        const searchInputContainer = document.createElement('div');
        searchInputContainer.className = 'search-input-container';
        
        const searchInput = document.createElement('input');
        searchInput.type = 'text';
        searchInput.id = 'search-query';
        searchInput.placeholder = t.placeholder;
        searchInput.autocomplete = 'off';
        
        searchInputContainer.appendChild(searchInput);
        searchWrapper.appendChild(searchInputContainer);

        // Commune dropdown
        const communeDropdown = createFilterableDropdown(
            'commune',
            communes,
            t.allCommunes,
            t.searchPlaceholder
        );
        searchWrapper.appendChild(communeDropdown);

        // Product dropdown
        const productDropdown = createFilterableDropdown(
            'product',
            products,
            t.allProducts,
            t.searchPlaceholder
        );
        searchWrapper.appendChild(productDropdown);

        // Search button
        const searchButton = document.createElement('button');
        searchButton.className = 'search-button';
        searchButton.textContent = t.searchButton;
        searchButton.type = 'button';
        searchButton.addEventListener('click', triggerSearch);
        searchWrapper.appendChild(searchButton);

        searchContainer.appendChild(searchWrapper);

        // Debounced input handler
        const debouncedInputHandler = debounce(() => {
            document.dispatchEvent(new CustomEvent('searchInputChanged'));
        }, 500);

        // Add input event listener with debounce
        searchInput.addEventListener('input', debouncedInputHandler);

        // Enter key support - immediate search without debounce
        searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                triggerSearch();
            }
        });
    }

    function triggerSearch() {
        const event = new CustomEvent('searchTriggered');
        document.dispatchEvent(event);
    }

    // Close dropdowns when clicking outside
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.filterable-dropdown')) {
            document.querySelectorAll('.dropdown-options').forEach(opt => {
                opt.style.display = 'none';
            });
        }
    });

    // Initial render
    await renderSearchBar();

    // Re-render on language change
    document.addEventListener('stateChange', renderSearchBar);
});
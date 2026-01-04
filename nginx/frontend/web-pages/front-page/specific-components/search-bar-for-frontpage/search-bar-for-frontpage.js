import { getLanguage, fetchProducts, fetchCommunes } from '../../../0-shared-components/utils/shared-functions.js';
import { sanitizeText } from '../../../0-shared-components/utils/sanitizer.js';

document.addEventListener('DOMContentLoaded', () => {
    const searchContainer = document.getElementById('search-container');

    const translations = {
        es: {
            placeholder: "Introduzca un término de búsqueda.",
            button: "Buscar",
            searchPlaceholder: "Buscar comuna...",
            searchProductPlaceholder: "Buscar producto..."
        },
        en: {
            placeholder: "Enter a search term.",
            button: "Search",
            searchPlaceholder: "Search commune...",
            searchProductPlaceholder: "Search product..."
        }
    };

    function createFilterableDropdown(options, placeholder, className, id) {
        // Create dropdown container
        const dropdown = document.createElement('div');
        dropdown.className = `filterable-dropdown ${className}`;
        dropdown.setAttribute('data-dropdown-id', id);
        
        // Selected display
        const selected = document.createElement('div');
        selected.className = 'dropdown-selected';
        selected.setAttribute('data-value', '');
        selected.textContent = sanitizeText(options[0]); // SAFE: First option (All)
        
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
        searchInput.placeholder = placeholder;
        searchInput.autocomplete = 'off';
        
        // Options list
        const optionsList = document.createElement('div');
        optionsList.className = 'options-list';
        
        // Create option elements (SANITIZED)
        options.forEach(option => {
            const optionDiv = document.createElement('div');
            optionDiv.className = 'dropdown-option';
            const safeOption = sanitizeText(option); // SAFE: Sanitize admin-controlled data
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

    function initializeDropdownFunctionality() {
        const dropdowns = document.querySelectorAll('.filterable-dropdown');
        
        dropdowns.forEach(dropdown => {
            const selected = dropdown.querySelector('.dropdown-selected');
            const options = dropdown.querySelector('.dropdown-options');
            const search = dropdown.querySelector('.dropdown-search');
            const allOptions = dropdown.querySelectorAll('.dropdown-option');
            
            // Toggle dropdown
            selected.addEventListener('click', (e) => {
                e.stopPropagation();
                closeAllDropdowns();
                options.style.display = options.style.display === 'block' ? 'none' : 'block';
                if (options.style.display === 'block') {
                    search.focus();
                    search.value = '';
                    filterOptions('');
                }
            });
            
            // Filter options
            function filterOptions(searchTerm) {
                allOptions.forEach(option => {
                    const text = option.textContent.toLowerCase();
                    if (text.includes(searchTerm.toLowerCase())) {
                        option.style.display = 'block';
                    } else {
                        option.style.display = 'none';
                    }
                });
            }
            
            search.addEventListener('input', (e) => {
                filterOptions(e.target.value);
            });
            
            // Select option
            allOptions.forEach(option => {
                option.addEventListener('click', () => {
                    const optionText = option.textContent;
                    selected.textContent = optionText;
                    const arrow = document.createElement('span');
                    arrow.className = 'dropdown-arrow';
                    arrow.textContent = '▼';
                    selected.appendChild(arrow);
                    selected.setAttribute('data-value', option.getAttribute('data-value'));
                    options.style.display = 'none';
                });
            });
            
            options.addEventListener('click', (e) => {
                e.stopPropagation();
            });
        });
        
        function closeAllDropdowns() {
            document.querySelectorAll('.dropdown-options').forEach(options => {
                options.style.display = 'none';
            });
        }
        
        document.addEventListener('click', closeAllDropdowns);
    }

    async function renderSearchBar() {
        const currentLang = getLanguage();
        const t = translations[currentLang];
        
        const currentQuery = document.getElementById('search-query')?.value || '';
        const currentCommuneValue = document.querySelector('[data-dropdown-id="commune"] .dropdown-selected')?.getAttribute('data-value') || '';
        const currentProductValue = document.querySelector('[data-dropdown-id="product"] .dropdown-selected')?.getAttribute('data-value') || '';
        
        const products = await fetchProducts();
        const communes = await fetchCommunes();
        
        const allCommunesText = currentLang === 'es' ? 'Todas Las Comunas' : 'All Communes';
        const allProductsText = currentLang === 'es' ? 'Todos Los Productos' : 'All Products';
        
        // SAFE: Sanitize all product/commune names
        const communeNames = [allCommunesText, ...communes.map(c => sanitizeText(c.name))];
        const productNames = [allProductsText, ...products.map(p => sanitizeText(currentLang === 'es' ? p.name_es : p.name_en))];

        // Create container
        const searchFlexContainer = document.createElement('div');
        searchFlexContainer.className = 'search-flex-container';
        
        // Create dropdowns
        const placesDropdown = createFilterableDropdown(communeNames, t.searchPlaceholder, 'commune-dropdown', 'commune');
        const productsDropdown = createFilterableDropdown(productNames, t.searchProductPlaceholder, 'product-dropdown', 'product');
        
        // Create search input
        const searchInputContainer = document.createElement('div');
        searchInputContainer.className = 'search-input-container';
        const searchInput = document.createElement('input');
        searchInput.type = 'text';
        searchInput.id = 'search-query';
        searchInput.placeholder = t.placeholder;
        searchInput.value = currentQuery;
        searchInputContainer.appendChild(searchInput);
        
        // Create search button
        const searchButton = document.createElement('button');
        searchButton.className = 'search-button';
        searchButton.id = 'search-btn';
        searchButton.textContent = t.button;
        
        // Assemble
        searchFlexContainer.appendChild(placesDropdown);
        searchFlexContainer.appendChild(productsDropdown);
        searchFlexContainer.appendChild(searchInputContainer);
        searchFlexContainer.appendChild(searchButton);
        
        searchContainer.textContent = ''; // Clear
        searchContainer.appendChild(searchFlexContainer);
        
        initializeDropdownFunctionality();
        
        // Restore previous selections
        if (currentCommuneValue && currentCommuneValue !== allCommunesText) {
            const communeDropdown = document.querySelector('[data-dropdown-id="commune"]');
            if (communeDropdown && communeNames.includes(currentCommuneValue)) {
                const selected = communeDropdown.querySelector('.dropdown-selected');
                selected.textContent = currentCommuneValue;
                const arrow = document.createElement('span');
                arrow.className = 'dropdown-arrow';
                arrow.textContent = '▼';
                selected.appendChild(arrow);
                selected.setAttribute('data-value', currentCommuneValue);
            }
        }
        
        if (currentProductValue && currentProductValue !== allProductsText) {
            const productDropdown = document.querySelector('[data-dropdown-id="product"]');
            if (productDropdown && productNames.includes(currentProductValue)) {
                const selected = productDropdown.querySelector('.dropdown-selected');
                selected.textContent = currentProductValue;
                const arrow = document.createElement('span');
                arrow.className = 'dropdown-arrow';
                arrow.textContent = '▼';
                selected.appendChild(arrow);
                selected.setAttribute('data-value', currentProductValue);
            }
        }
        
        // Add search functionality
        document.getElementById('search-btn')?.addEventListener('click', () => {
            document.dispatchEvent(new CustomEvent('searchTriggered'));
        });
        
        document.getElementById('search-query')?.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                document.dispatchEvent(new CustomEvent('searchTriggered'));
            }
        });
    }

    document.addEventListener("languageChange", () => {
        renderSearchBar();
    });

    renderSearchBar();
});
import { getLanguage, fetchProducts, fetchCommunes } from '../../../0-shared-components/utils/shared-functions.js';
import { sanitizeText } from '../../../0-shared-components/utils/sanitizer.js';

document.addEventListener('DOMContentLoaded', () => {
    const searchContainer = document.getElementById('search-container');

    const translations = {
        es: {
            placeholder: 'Introduzca un término de búsqueda.',
            button: 'Buscar',
            searchPlaceholder: 'Buscar comuna...',
            searchProductPlaceholder: 'Buscar producto...',
        },
        en: {
            placeholder: 'Enter a search term.',
            button: 'Search',
            searchPlaceholder: 'Search commune...',
            searchProductPlaceholder: 'Search product...',
        },
    };

    /**
     * Create a filterable dropdown using DOM APIs only
     */
    function createFilterableDropdown(options, placeholder, className, id) {
        const dropdown = document.createElement('div');
        dropdown.className = `filterable-dropdown ${className}`;
        dropdown.dataset.dropdownId = id;

        // Selected display
        const selected = document.createElement('div');
        selected.className = 'dropdown-selected';
        selected.dataset.value = '';

        selected.textContent = sanitizeText(options[0]);
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

        options.forEach(option => {
            const optionDiv = document.createElement('div');
            optionDiv.className = 'dropdown-option';

            const safeOption = sanitizeText(option);
            optionDiv.dataset.value = safeOption;
            optionDiv.textContent = safeOption;

            optionsList.appendChild(optionDiv);
        });

        optionsContainer.appendChild(searchInput);
        optionsContainer.appendChild(optionsList);

        dropdown.appendChild(selected);
        dropdown.appendChild(optionsContainer);

        return dropdown;
    }

    /**
     * Dropdown behavior (event delegation, no inline handlers)
     */
    function initializeDropdownFunctionality() {
        const dropdowns = document.querySelectorAll('.filterable-dropdown');

        dropdowns.forEach(dropdown => {
            const selected = dropdown.querySelector('.dropdown-selected');
            const options = dropdown.querySelector('.dropdown-options');
            const search = dropdown.querySelector('.dropdown-search');
            const allOptions = dropdown.querySelectorAll('.dropdown-option');

            selected.addEventListener('click', e => {
                e.stopPropagation();
                closeAllDropdowns();
                options.style.display = options.style.display === 'block' ? 'none' : 'block';

                if (options.style.display === 'block') {
                    search.value = '';
                    search.focus();
                    filterOptions('');
                }
            });

            function filterOptions(term) {
                const lower = term.toLowerCase();
                allOptions.forEach(option => {
                    option.style.display = option.textContent.toLowerCase().includes(lower)
                        ? 'block'
                        : 'none';
                });
            }

            search.addEventListener('input', e => {
                filterOptions(e.target.value);
            });

            allOptions.forEach(option => {
                option.addEventListener('click', () => {
                    selected.textContent = option.textContent;

                    const arrow = document.createElement('span');
                    arrow.className = 'dropdown-arrow';
                    arrow.textContent = '▼';
                    selected.appendChild(arrow);

                    selected.dataset.value = option.dataset.value;
                    options.style.display = 'none';
                });
            });

            options.addEventListener('click', e => e.stopPropagation());
        });

        function closeAllDropdowns() {
            document.querySelectorAll('.dropdown-options').forEach(o => {
                o.style.display = 'none';
            });
        }

        document.addEventListener('click', closeAllDropdowns);
    }

    /**
     * Render search bar safely
     */
    async function renderSearchBar() {
        const currentLang = getLanguage();
        const t = translations[currentLang];

        // Preserve state
        const currentQuery =
            document.getElementById('search-query')?.value || '';
        const currentCommuneValue =
            document.querySelector('[data-dropdown-id="commune"] .dropdown-selected')
                ?.dataset.value || '';
        const currentProductValue =
            document.querySelector('[data-dropdown-id="product"] .dropdown-selected')
                ?.dataset.value || '';

        const products = await fetchProducts();
        const communes = await fetchCommunes();

        const allCommunesText =
            currentLang === 'es' ? 'Todas Las Comunas' : 'All Communes';
        const allProductsText =
            currentLang === 'es' ? 'Todos Los Productos' : 'All Products';

        const communeNames = [
            allCommunesText,
            ...communes.map(c => sanitizeText(c.name)),
        ];

        const productNames = [
            allProductsText,
            ...products.map(p =>
                sanitizeText(currentLang === 'es' ? p.name_es : p.name_en)
            ),
        ];

        const searchFlex = document.createElement('div');
        searchFlex.className = 'search-flex-container';

        const placesDropdown = createFilterableDropdown(
            communeNames,
            t.searchPlaceholder,
            'commune-dropdown',
            'commune'
        );

        const productsDropdown = createFilterableDropdown(
            productNames,
            t.searchProductPlaceholder,
            'product-dropdown',
            'product'
        );

        const searchInputContainer = document.createElement('div');
        searchInputContainer.className = 'search-input-container';

        const searchInput = document.createElement('input');
        searchInput.type = 'text';
        searchInput.id = 'search-query';
        searchInput.placeholder = t.placeholder;
        searchInput.value = currentQuery;
        searchInputContainer.appendChild(searchInput);

        const searchButton = document.createElement('button');
        searchButton.className = 'search-button';
        searchButton.id = 'search-btn';
        searchButton.textContent = t.button;

        searchFlex.appendChild(placesDropdown);
        searchFlex.appendChild(productsDropdown);
        searchFlex.appendChild(searchInputContainer);
        searchFlex.appendChild(searchButton);

        searchContainer.textContent = '';
        searchContainer.appendChild(searchFlex);

        initializeDropdownFunctionality();

        // Restore selections
        if (currentCommuneValue && communeNames.includes(currentCommuneValue)) {
            const selected =
                document.querySelector('[data-dropdown-id="commune"] .dropdown-selected');
            if (selected) {
                selected.textContent = currentCommuneValue;
                const arrow = document.createElement('span');
                arrow.className = 'dropdown-arrow';
                arrow.textContent = '▼';
                selected.appendChild(arrow);
                selected.dataset.value = currentCommuneValue;
            }
        }

        if (currentProductValue && productNames.includes(currentProductValue)) {
            const selected =
                document.querySelector('[data-dropdown-id="product"] .dropdown-selected');
            if (selected) {
                selected.textContent = currentProductValue;
                const arrow = document.createElement('span');
                arrow.className = 'dropdown-arrow';
                arrow.textContent = '▼';
                selected.appendChild(arrow);
                selected.dataset.value = currentProductValue;
            }
        }

        searchButton.addEventListener('click', () => {
            document.dispatchEvent(new CustomEvent('searchTriggered'));
        });

        searchInput.addEventListener('keypress', e => {
            if (e.key === 'Enter') {
                document.dispatchEvent(new CustomEvent('searchTriggered'));
            }
        });
    }

    document.addEventListener('languageChange', renderSearchBar);

    renderSearchBar();
});

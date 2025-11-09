import { getLanguage, fetchProducts, fetchCommunes } from '../../../0-shared-components/utils/shared-functions.js';

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
        const dropdownHTML = `
            <div class="filterable-dropdown ${className}" data-dropdown-id="${id}">
                <div class="dropdown-selected" data-value="${options[0].toLowerCase().replace(/ /g, '-')}">
                    ${options[0]}
                    <span class="dropdown-arrow">▼</span>
                </div>
                <div class="dropdown-options" style="display: none;">
                    <input type="text" class="dropdown-search" placeholder="${placeholder}" autocomplete="off">
                    <div class="options-list">
                        ${options.map(option => `
                            <div class="dropdown-option" data-value="${option.toLowerCase().replace(/ /g, '-')}">${option}</div>
                        `).join('')}
                    </div>
                </div>
            </div>
        `;
        return dropdownHTML;
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
                    selected.innerHTML = `${option.textContent} <span class="dropdown-arrow">▼</span>`;
                    selected.setAttribute('data-value', option.getAttribute('data-value'));
                    options.style.display = 'none';
                });
            });
            
            // Prevent dropdown from closing when clicking inside
            options.addEventListener('click', (e) => {
                e.stopPropagation();
            });
        });
        
        // Close dropdowns when clicking outside
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
        
        // Fetch products and communes from API
        const products = await fetchProducts();
        const communes = await fetchCommunes();
        
        // Add "All" option at the beginning
        const allCommunesText = currentLang === 'es' ? 'Todas Las Comunas' : 'All Communes';
        const allProductsText = currentLang === 'es' ? 'Todos Los Productos' : 'All Products';
        
        const communeNames = [allCommunesText, ...communes.map(c => c.name)];
        const productNames = [allProductsText, ...products.map(p => currentLang === 'es' ? p.name_es : p.name_en)];

        const placesDropdown = createFilterableDropdown(
            communeNames, 
            t.searchPlaceholder, 
            'places-dropdown', 
            'places'
        );
        
        const productsDropdown = createFilterableDropdown(
            productNames, 
            t.searchProductPlaceholder, 
            'products-dropdown', 
            'products'
        );

        const searchBarContent = `
            <div class="search-flex-container">
                ${placesDropdown}
                ${productsDropdown}
                <div class="search-input-container">
                    <input type="text" id="search-query" placeholder="${t.placeholder}">
                </div>
                <button class="search-button" id="search-btn">${t.button}</button>
            </div>
        `;

        searchContainer.innerHTML = searchBarContent;
        initializeDropdownFunctionality();
        
        // Add search button functionality
        document.getElementById('search-btn')?.addEventListener('click', () => {
            // Trigger results update
            document.dispatchEvent(new CustomEvent('searchTriggered'));
        });
        
        // Also trigger search on Enter key
        document.getElementById('search-query')?.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                document.dispatchEvent(new CustomEvent('searchTriggered'));
            }
        });
    }

    document.addEventListener("languageChange", () => {
        renderSearchBar();
    });

    // Listen for search trigger
    document.addEventListener("searchTriggered", () => {
        // Trigger results refresh (result-container will handle this)
        document.dispatchEvent(new CustomEvent('resultsRefresh'));
    });

    renderSearchBar();
});
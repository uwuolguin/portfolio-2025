// Enhanced search-bar-for-frontpage.js
import { getLanguage } from '../../../0-shared-components/utils/shared-functions.js';

document.addEventListener('DOMContentLoaded', () => {
    const searchContainer = document.getElementById('search-container');

    const translations = {
        es: {
            places: ["Todas Las Comunas", "La Florida", "Lo Curro", "Los Troncos", "Otra"],
            products: ["Todos Los Productos", "Fiambrería", "Lácteos", "Legumbres", "Otro"],
            placeholder: "Introduzca un término de búsqueda.",
            button: "Buscar",
            searchPlaceholder: "Buscar comuna...",
            searchProductPlaceholder: "Buscar producto..."
        },
        en: {
            places: ["All Communes", "La Florida", "Lo Curro", "Los Troncos", "Other"],
            products: ["All Products", "Fiambrería", "Dairy", "Legumes", "Other"],
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
            const optionsList = dropdown.querySelector('.options-list');
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

    function renderSearchBar() {
        const currentLang = getLanguage();
        const filterOptionsPlaces = translations[currentLang].places;
        const filterOptionsProducts = translations[currentLang].products;

        const placesDropdown = createFilterableDropdown(
            filterOptionsPlaces, 
            translations[currentLang].searchPlaceholder, 
            'places-dropdown', 
            'places'
        );
        
        const productsDropdown = createFilterableDropdown(
            filterOptionsProducts, 
            translations[currentLang].searchProductPlaceholder, 
            'products-dropdown', 
            'products'
        );

        const searchBarContent = `
            <div class="search-flex-container">
                ${placesDropdown}
                ${productsDropdown}
                <div class="search-input-container">
                    <input type="text" placeholder="${translations[currentLang].placeholder}">
                </div>
                <button class="search-button">${translations[currentLang].button}</button>
            </div>
        `;

        searchContainer.innerHTML = searchBarContent;
        initializeDropdownFunctionality();
    }

    document.addEventListener("languageChange", () => {
        renderSearchBar();
    });
    
    renderSearchBar();
});
import {
    getLanguage,
    getLoginState,
    setLoginState,
    setCSRFToken
} from '../../../0-shared-components/utils/shared-functions.js';

import {
    sanitizeAPIResponse,
    buildBusinessCard,
    sanitizeText
} from '../../../0-shared-components/utils/sanitizer.js';

document.addEventListener('DOMContentLoaded', () => {
    const resultsContainer = document.getElementById('results-container');

    const translations = {
        es: {
            noResults: 'No se encontraron resultados',
            loading: 'Cargando...',
            error: 'Error al cargar los resultados',
            page: 'Página',
            previous: 'Anterior',
            next: 'Siguiente'
        },
        en: {
            noResults: 'No results found',
            loading: 'Loading...',
            error: 'Error loading results',
            page: 'Page',
            previous: 'Previous',
            next: 'Next'
        }
    };

    let currentPage = 1;
    const resultsPerPage = 20;

    function clearResults() {
        resultsContainer.textContent = '';
    }

    function showLoading() {
        const lang = getLanguage();
        const t = translations[lang];
        clearResults();
        
        const loading = document.createElement('div');
        loading.className = 'loading-message';
        loading.textContent = t.loading;
        resultsContainer.appendChild(loading);
    }

    function showError() {
        const lang = getLanguage();
        const t = translations[lang];
        clearResults();
        
        const error = document.createElement('div');
        error.className = 'error-message';
        error.textContent = t.error;
        resultsContainer.appendChild(error);
    }

    function showNoResults() {
        const lang = getLanguage();
        const t = translations[lang];
        clearResults();
        
        const noResults = document.createElement('div');
        noResults.className = 'no-results-message';
        noResults.textContent = t.noResults;
        resultsContainer.appendChild(noResults);
    }

    async function fetchResults(query, commune, product, page = 1) {
        try {
            showLoading();

            const params = new URLSearchParams({
                lang: getLanguage(),
                limit: resultsPerPage,
                offset: (page - 1) * resultsPerPage
            });

            if (query && query.trim()) {
                params.append('q', sanitizeText(query));
            }
            if (commune && commune !== 'Todas Las Comunas' && commune !== 'All Communes') {
                params.append('commune', sanitizeText(commune));
            }
            if (product && product !== 'Todos Los Productos' && product !== 'All Products') {
                params.append('product', sanitizeText(product));
            }

            const response = await fetch(`/api/v1/companies/search?${params}`, {
                credentials: 'include',
                headers: {
                    'X-Correlation-ID': `search_${Date.now()}`
                }
            });

            if (!response.ok) {
                throw new Error('Search failed');
            }

            const rawData = await response.json();
            
            const companies = sanitizeAPIResponse(rawData);

            displayResults(companies, page);

        } catch (error) {
            console.error('Search error:', error);
            showError();
        }
    }

    function displayResults(companies, page) {
        const lang = getLanguage();

        clearResults();

        if (!companies || companies.length === 0) {
            showNoResults();
            return;
        }

        // Create grid container
        const grid = document.createElement('div');
        grid.className = 'results-grid';

        companies.forEach(company => {
            const card = buildBusinessCard(company, lang);
            grid.appendChild(card);
        });

        resultsContainer.appendChild(grid);

        // Add pagination
        if (companies.length === resultsPerPage) {
            createPagination(page);
        }
    }

    function createPagination(currentPage) {
        const lang = getLanguage();
        const t = translations[lang];

        const paginationContainer = document.createElement('div');
        paginationContainer.className = 'pagination-container';

        // Previous button
        if (currentPage > 1) {
            const prevLink = document.createElement('a');
            prevLink.href = '#';
            prevLink.className = 'page-link';
            prevLink.textContent = t.previous;
            prevLink.addEventListener('click', (e) => {
                e.preventDefault();
                performSearch(currentPage - 1);
            });
            paginationContainer.appendChild(prevLink);
        }

        // Current page indicator
        const pageInfo = document.createElement('span');
        pageInfo.className = 'page-info';
        pageInfo.textContent = `${t.page} ${currentPage}`;
        paginationContainer.appendChild(pageInfo);

        // Next button
        const nextLink = document.createElement('a');
        nextLink.href = '#';
        nextLink.className = 'page-link';
        nextLink.textContent = t.next;
        nextLink.addEventListener('click', (e) => {
            e.preventDefault();
            performSearch(currentPage + 1);
        });
        paginationContainer.appendChild(nextLink);

        resultsContainer.appendChild(paginationContainer);
    }

    function performSearch(page = 1) {
        currentPage = page;

        const query = document.getElementById('search-query')?.value || '';
        
        const communeDropdown = document.querySelector('[data-dropdown-id="commune"] .dropdown-selected');
        const commune = communeDropdown?.dataset.value || '';
        
        const productDropdown = document.querySelector('[data-dropdown-id="product"] .dropdown-selected');
        const product = productDropdown?.dataset.value || '';

        fetchResults(query, commune, product, page);
    }

    // Listen for search trigger
    document.addEventListener('searchTriggered', () => {
        performSearch(1);
    });

    // Initial load - show all companies
    document.addEventListener('DOMContentLoaded', () => {
        performSearch(1);
    });

    // Re-render on language change
    document.addEventListener('languageChange', () => {
        performSearch(currentPage);
    });
});
import { getLanguage, apiRequest } from '../../../0-shared-components/utils/shared-functions.js';

document.addEventListener('DOMContentLoaded', () => {
    const resultsContainer = document.getElementById('results-container');
    const cardsPerPage = 5;
    const numbersPerPagination = 3;
    let currentPage = 1;

    const renderCards = (companies) => {
        const startIndex = (currentPage - 1) * cardsPerPage;
        const endIndex = startIndex + cardsPerPage;
        const companiesToDisplay = companies.slice(startIndex, endIndex);

        let cardsHtml = '';
        companiesToDisplay.forEach(company => {
            cardsHtml += `
                <div class="business-card">
                    <div class="card-picture">
                        <img src="http://localhost/files/${company.image}" alt="Product Image ${company.id}">
                    </div>
                    <div class="card-details">
                        <h3 class="business-name">${company.name}</h3>
                        <p class="concise-description">${company.description}</p>
                        <p class="location">${company.address}</p>
                        <p class="phone"> ${company.phone}</p>
                        <p class="mail"> ${company.email}</p>
                    </div>
                </div>
            `;
        });
        return cardsHtml;
    };

    const renderPagination = () => {
        let half = Math.floor(numbersPerPagination / 2);
        let startPage = Math.max(1, currentPage - half);
        let endPage = startPage + numbersPerPagination - 1;

        let paginationHtml = `
            <div class="pagination-container">
                <a href="#" class="page-link prev-link">&laquo;</a>
        `;

        for (let i = startPage; i <= endPage; i++) {
            paginationHtml += `
                <a href="#" class="page-link ${i === currentPage ? 'active' : ''}" data-page="${i}">${i}</a>
            `;
        }

        paginationHtml += `
                <a href="#" class="page-link next-link">&raquo;</a>
            </div>
        `;

        return paginationHtml;
    };

    const fetchAndRender = async () => {
        try {
            const currentLanguage = getLanguage();
            
            // Get search parameters from search bar if available
            const searchQuery = document.getElementById('search-query')?.value || '';
            const communeFilter = document.querySelector('[data-dropdown-id="commune"] .dropdown-selected')?.getAttribute('data-value') || '';
            const productFilter = document.querySelector('[data-dropdown-id="product"] .dropdown-selected')?.getAttribute('data-value') || '';
            
            // Build API URL with query parameters
            const params = new URLSearchParams({
                lang: currentLanguage,
                limit: cardsPerPage.toString(),
                offset: ((currentPage - 1) * cardsPerPage).toString()
            });
            
            if (searchQuery) params.append('q', searchQuery);
            if (communeFilter) params.append('commune', communeFilter);
            if (productFilter) params.append('product', productFilter);
            
            const response = await apiRequest(`/api/v1/companies/search?${params.toString()}`);
            
            if (!response.ok) {
                throw new Error('Failed to fetch companies');
            }
            
            const companies = await response.json();
            
            // Transform API response to match expected format
            const transformedCompanies = companies.map(company => ({
                id: company.uuid,
                name: company.name,
                description: company.description,
                address: company.address,
                phone: company.phone,
                email: company.email,
                image: company.img_url || 'https://via.placeholder.com/400x220?text=No+Image'
            }));

            let cardsHtml = '';
            if (transformedCompanies.length > 0) {
                cardsHtml = renderCards(transformedCompanies);
            } else {
                cardsHtml = `
                    <div style="text-align: center; padding: 40px; color: #666;">
                        ${currentLanguage === 'es' ? 'No se encontraron empresas' : 'No companies found'}
                    </div>
                `;
            }

            const paginationHtml = renderPagination();

            resultsContainer.innerHTML = `
                <div class="results-grid">${cardsHtml}</div>
                ${paginationHtml}
            `;

        } catch (error) {
            console.error("Error fetching companies:", error);
            resultsContainer.innerHTML = `
                <div style="text-align: center; padding: 40px; color: #d32f2f;">
                    ${getLanguage() === 'es' ? 'Error al cargar las empresas' : 'Error loading companies'}
                </div>
            `;
        }
    };

    resultsContainer.addEventListener('click', (e) => {
        const link = e.target.closest('.page-link');
        if (!link) return; 
        e.preventDefault();

        if (link.classList.contains('prev-link')) {
            currentPage = Math.max(1, currentPage - 1);
        } else if (link.classList.contains('next-link')) {
            currentPage = currentPage + 1;
        } else {
            currentPage = parseInt(link.dataset.page);
        }

        fetchAndRender();
    });

    document.addEventListener("languageChange", () => {
        fetchAndRender();
    });
    // Listen for search trigger
    document.addEventListener("searchTriggered", () => {
        currentPage = 1; // Reset to first page
        fetchAndRender();
    });

    // Listen for results refresh
    document.addEventListener("resultsRefresh", () => {
        fetchAndRender();
    });

    fetchAndRender();
});
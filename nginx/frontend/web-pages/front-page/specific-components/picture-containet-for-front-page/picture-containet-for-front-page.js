document.addEventListener('DOMContentLoaded', () => {
    const imageContainer = document.getElementById('picture-container');

    // Clear container safely
    imageContainer.textContent = '';

    const wrapper = document.createElement('div');
    wrapper.className = 'image-container';

    const img = document.createElement('img');
    img.src = '/files/test_pictures/background-picture.jpg';
    img.alt = 'Description of the image';

    wrapper.appendChild(img);
    imageContainer.appendChild(wrapper);
});

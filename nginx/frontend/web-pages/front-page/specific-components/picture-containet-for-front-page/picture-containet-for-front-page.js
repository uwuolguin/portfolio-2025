document.addEventListener('DOMContentLoaded', () => {
    const imageContainer = document.getElementById('picture-container');

    const imageContent = `
        <div class="image-container">
            <img src="/files/pictures/background-picture.jpg" 
                 alt="Description of the image">
        </div>
    `;

    imageContainer.innerHTML = imageContent;
});
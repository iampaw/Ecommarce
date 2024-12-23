function toggleMenu() {
    var toggleBar = document.getElementById('toggle-bar');
    if (toggleBar.style.display === 'none') {
        toggleBar.style.display = 'block';
    } else {
        toggleBar.style.display = 'none';
    }
}

function toggleBar() {
    const toggleBar = document.getElementById('toggle-bar');
    if (toggleBar.style.display === 'none' || toggleBar.style.display === '') {
        toggleBar.style.display = 'block';
    } else {
        toggleBar.style.display = 'none';
    }
}

document.addEventListener('DOMContentLoaded', function() {
    const cartIcon = document.getElementById('cart-icon');
    const shoppingCart = document.getElementById('shoppingCart');
    const closeBtn = document.querySelector('.close-btn');

    cartIcon.addEventListener('click', (event) => {
        event.preventDefault(); 
        shoppingCart.style.right = '0'; 
    });

    closeBtn.addEventListener('click', () => {
        shoppingCart.style.right = '-100%'; 
    });
});

//script navbar
const menuToggle = document.getElementById('mobile-menu');
menuToggle.addEventListener('click', () => {
    const navLinks = document.querySelector('.nav-links');
    navLinks.classList.toggle('active'); // Mengaktifkan atau menonaktifkan class active
});

// POP UP
document.querySelector('.checkout-btn').addEventListener('click', function (event) {
    const isAuthenticated = {{ user.is_authenticated|yesno:"true,false" }};  // Convert Django boolean to JS
    if (isAuthenticated) {
        const cartItems = document.querySelectorAll('.cart-item'); // Adjust selector as needed
        if (cartItems.length === 0) {
            event.preventDefault();
            const popup = document.getElementById('empty-cart-popup');
            popup.classList.add('show');
            setTimeout(() => {
                popup.classList.remove('show');
            }, 3000);
        }
    } else {
        window.location.href = "{% url 'signup' %}";
    }
});



document.addEventListener('DOMContentLoaded', function() {
    const searchInput = document.getElementById('searchInput');
    const makananList = document.querySelectorAll('.makanan');
    const makanan2List = document.querySelectorAll('.makanan2');  // Menambahkan list untuk makanan2
    
    // Event listener untuk input pencarian
    searchInput.addEventListener('input', function() {
        const query = searchInput.value.toLowerCase();

        // Mencari makanan pada list makanan
        makananList.forEach(makanan => {
            const makananName = makanan.querySelector('.makanan-name').textContent.toLowerCase();

            if (makananName.includes(query)) {
                makanan.scrollIntoView({ behavior: 'smooth', block: 'center' });
                makanan.style.border = '2px solid rgb(103, 60, 0)'; // Highlight makanan
            } else {
                makanan.style.border = 'none'; // Menghapus highlight jika tidak cocok
            }
        });

        // Mencari makanan2 pada list makanan2
        makanan2List.forEach(makanan2 => {
            const makanan2Name = makanan2.querySelector('.makanan-name').textContent.toLowerCase();

            if (makanan2Name.includes(query)) {
                makanan2.scrollIntoView({ behavior: 'smooth', block: 'center' });
                makanan2.style.border = '2px solid rgb(103, 60, 0)'; // Highlight makanan2
            } else {
                makanan2.style.border = 'none'; // Menghapus highlight jika tidak cocok
            }
        });
    });
});


function filterCategory(category) {
    // Get all items
    const items = document.querySelectorAll('.makanan2');

    // Loop through items and show/hide based on category
    items.forEach(item => {
        const itemCategory = item.getAttribute('data-category');
        
        if (category === 'all' || itemCategory === category) {
            item.style.display = 'block'; // Show item
        } else {
            item.style.display = 'none'; // Hide item
        }
    });
}


function filterCategory(category) {
    const items = document.querySelectorAll('.makanan2'); // Pilih semua elemen makanan2

    items.forEach(item => {
        const itemCategory = item.getAttribute('data-category'); // Ambil kategori dari atribut data-category
        
        if (category === 'all' || itemCategory === category) {
            item.style.display = 'block'; // Tampilkan elemen
        } else {
            item.style.display = 'none'; // Sembunyikan elemen
        }
    });
}



const cartIcon = document.getElementById("cart-icon");
const cartSidebar = document.querySelector(".cart-sidebar");
const cartItemsContainer = document.querySelector(".cart-items");
const closeBtn = document.querySelector(".close-btn");

// Seleksi semua tombol "Add to Cart" dari kedua kategori
const addToCartButtons = document.querySelectorAll(".makanan .btn-add-to-card, .makanan2 .btn-add-to-card");

// Fungsi untuk menampilkanbut sidebar keranjang
function openCartSidebar() {
    cartSidebar.style.right = "0";
}

// Fungsi untuk menutup sidebar keranjang
function closeCartSidebar() {
    cartSidebar.style.right = "-100%";
}

// Fungsi untuk menghapus item dari keranjang
function removeCartItem(cartItem) {
    cartItem.remove();
}

// Fungsi untuk menambah jumlah item
function increaseQuantity(event) {
const cartItem = event.target.closest(".cart-item");
const quantityDisplay = cartItem.querySelector(".quantity-display");
const priceDisplay = cartItem.querySelector(".item-price");
const unitPrice = parseFloat(cartItem.getAttribute("data-unit-price"));

let quantity = parseInt(quantityDisplay.textContent);
quantity++;
quantityDisplay.textContent = quantity;

// Format harga sebagai Rupiah
priceDisplay.textContent = new Intl.NumberFormat('id-ID', {
    style: 'currency',
    currency: 'IDR',
    minimumFractionDigits: 0
}).format(unitPrice * quantity);
}

// Fungsi untuk mengurangi jumlah item
function decreaseQuantity(event) {
const cartItem = event.target.closest(".cart-item");
const quantityDisplay = cartItem.querySelector(".quantity-display");
const priceDisplay = cartItem.querySelector(".item-price");
const unitPrice = parseFloat(cartItem.getAttribute("data-unit-price"));

let quantity = parseInt(quantityDisplay.textContent);

if (quantity > 1) {
    quantity--;
    quantityDisplay.textContent = quantity;

    // Format harga sebagai Rupiah
    priceDisplay.textContent = new Intl.NumberFormat('id-ID', {
        style: 'currency',
        currency: 'IDR',
        minimumFractionDigits: 0
    }).format(unitPrice * quantity);
} else {
    removeCartItem(cartItem);
}
}

// Fungsi untuk menambahkan item ke keranjang
function addToCart(event) {
const makananElement = event.target.closest(".makanan, .makanan2");
const stock = parseInt(makananElement.getAttribute("data-stock"));

if (stock === 0) {
    alert("Maaf, item ini sudah habis.");
    return;
}

const itemName = makananElement.querySelector(".makanan-name").textContent;
const itemPrice = parseFloat(makananElement.querySelector("p").textContent.replace(/[^0-9.-]+/g, ""));
const itemImageSrc = makananElement.querySelector("img").src;

// Lanjutkan untuk menambahkan item ke keranjang
const cart = JSON.parse(localStorage.getItem("cart")) || [];
const existingCartItem = Array.from(cartItemsContainer.children).find(item => 
    item.querySelector("h4").textContent === itemName
);

if (existingCartItem) {
    const quantityDisplay = existingCartItem.querySelector(".quantity-display");
    quantityDisplay.textContent = parseInt(quantityDisplay.textContent) + 1;
    const priceDisplay = existingCartItem.querySelector(".item-price");
    const unitPrice = parseFloat(existingCartItem.getAttribute("data-unit-price"));
    const newQuantity = parseInt(quantityDisplay.textContent);

    // Update tampilan harga
    priceDisplay.textContent = new Intl.NumberFormat('id-ID', {
        style: 'currency',
        currency: 'IDR',
        minimumFractionDigits: 0
    }).format(unitPrice * newQuantity);
} else {
    const cartItem = document.createElement("div");
    cartItem.classList.add("cart-item");
    cartItem.setAttribute("data-unit-price", itemPrice);
    cartItem.innerHTML = `
        <div style="display: flex; align-items: center; gap: 10px; width: 100%;">
            <img src="${itemImageSrc}" alt="${itemName}" width="50" height="50">
            <div style="flex-grow: 1;">
                <h4>${itemName}</h4>
                <p class="item-price">${new Intl.NumberFormat('id-ID', {
                    style: 'currency',
                    currency: 'IDR',
                    minimumFractionDigits: 0
                }).format(itemPrice)}</p>
            </div>
            <div class="quantity-controls" style="display: flex; align-items: center; gap: 5px;">
                <button class="quantity-btn decrease-btn">-</button>
                <span class="quantity-display">1</span>
                <button class="quantity-btn increase-btn">+</button>
            </div>
        </div>
    `;

    const increaseButton = cartItem.querySelector(".increase-btn");
    const decreaseButton = cartItem.querySelector(".decrease-btn");
    increaseButton.addEventListener("click", increaseQuantity);
    decreaseButton.addEventListener("click", decreaseQuantity);

    cartItemsContainer.appendChild(cartItem);
}

const existingItem = cart.find(item => item.name === itemName);
if (existingItem) {
    existingItem.quantity += 1;
} else {
    cart.push({
        name: itemName,
        price: itemPrice,
        image: itemImageSrc,
        quantity: 1
    });
}

localStorage.setItem("cart", JSON.stringify(cart));
}

// Event listener untuk tombol "Add to Cart"
addToCartButtons.forEach(button => {
    button.addEventListener("click", addToCart);
});

cartIcon.addEventListener("click", openCartSidebar);
closeBtn.addEventListener("click", closeCartSidebar);

document.addEventListener("scroll", function () {
const navbar = document.querySelector(".navbar"); // Pilih elemen navbar
if (window.scrollY > 0) { // Jika halaman digulir
    navbar.classList.add("scrolled");
} else {
    navbar.classList.remove("scrolled");
}
});
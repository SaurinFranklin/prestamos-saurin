// Filtra las tarjetas de préstamos mientras se escribe.
document.getElementById("inputBuscador").addEventListener("keyup", function () {
    const query = this.value.toLowerCase().trim();
    document.querySelectorAll(".card-prestamo-item").forEach((item) => {
        item.style.display = item.dataset.search.includes(query) ? "block" : "none";
    });
});

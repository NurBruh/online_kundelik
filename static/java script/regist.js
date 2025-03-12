document.addEventListener("DOMContentLoaded", function () {
    const form = document.getElementById("registrationForm");

    form.addEventListener("submit", function (event) {
        event.preventDefault(); // Предотвращаем стандартную отправку формы

        let isValid = true;
        const inputs = form.querySelectorAll("input, select");

        inputs.forEach(input => {
            if (input.value.trim() === "") {
                isValid = false;
                input.style.border = "2px solid red";
            } else {
                input.style.border = "none";
            }
        });

        if (isValid) {
            alert("Форма успешно отправлена!");
            form.submit(); // Если все поля заполнены, отправляем форму
        } else {
            alert("Пожалуйста, заполните все поля!");
        }
    });
});

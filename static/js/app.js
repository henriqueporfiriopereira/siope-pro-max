
let filesList = [];

document.addEventListener("DOMContentLoaded", ()=>{
    const dz = document.getElementById("dropzone");
    if(dz){
        dz.addEventListener("dragover", e=>{e.preventDefault(); dz.style.background="#ddd";});
        dz.addEventListener("drop", e=>{
            e.preventDefault();
            filesList = e.dataTransfer.files;
            dz.innerHTML = filesList.length + " arquivos";
        });

        loadChart();
    }
});

function uploadFiles(){
    let formData = new FormData();
    for(let f of filesList){
        formData.append("files", f);
    }

    fetch("/upload", {
        method:"POST",
        body:formData
    }).then(()=>location.reload());
}

function loadChart(){
    fetch("/api/chart")
    .then(r=>r.json())
    .then(data=>{
        new Chart(document.getElementById("chart"), {
            type:"bar",
            data:{
                labels:data.labels,
                datasets:[{label:"Correções", data:data.values}]
            }
        });
    });
}

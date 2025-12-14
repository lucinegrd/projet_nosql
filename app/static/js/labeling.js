function startLabeling() {
    const btn = document.getElementById('startBtn');
    const loading = document.getElementById('loading');
    const resultMsg = document.getElementById('resultMsg');

    btn.disabled = true;
    loading.style.display = 'block';
    
    // Simulation pour l'instant (On connectera l'API Tâche 4 plus tard)
    setTimeout(() => {
        loading.style.display = 'none';
        resultMsg.style.display = 'block';
        resultMsg.innerText = "Processus terminé ! 500 nouvelles annotations prédites.";
        btn.disabled = false;
    }, 3000);
}
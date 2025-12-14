async function loadStats() {
    try {
        const response = await fetch('/api/stats');
        const data = await response.json();

        // 1. Remplir les cartes
        document.getElementById('statsCards').innerHTML = `
            <div class="col-md-3"><div class="card bg-success text-white p-3"><h3>${data.mongo.total_proteins}</h3><small>Total Protéines</small></div></div>
            <div class="col-md-3"><div class="card bg-info text-white p-3"><h3>${data.mongo.labeled_proteins}</h3><small>Étiquetées</small></div></div>
            <div class="col-md-3"><div class="card bg-warning text-white p-3"><h3>${data.neo4j.isolated_proteins}</h3><small>Isolées</small></div></div>
            <div class="col-md-3"><div class="card bg-danger text-white p-3"><h3>${data.neo4j.total_similarities}</h3><small>Relations</small></div></div>
        `;

        // 2. Dessiner le Chart (Histogramme)
        const ctx = document.getElementById('labelChart').getContext('2d');
        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: ['Labellisées (Labeled)', 'Non-Labellisées (Unlabeled)'],
                datasets: [{
                    label: 'Nombre de protéines',
                    data: [data.mongo.labeled_proteins, data.mongo.unlabeled_proteins],
                    backgroundColor: ['#36a2eb', '#ff6384']
                }]
            },
            options: { scales: { y: { beginAtZero: true } } }
        });
    } catch (error) {
        console.error("Erreur lors du chargement des statistiques:", error);
        document.getElementById('statsCards').innerHTML = `<div class="col-12 text-center text-danger">Erreur de chargement des données.</div>`;
    }
}

// Lancer le chargement une fois le DOM prêt
document.addEventListener('DOMContentLoaded', loadStats);
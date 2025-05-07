import React, { useState } from 'react';
import axios from 'axios';
import { Bar } from 'react-chartjs-2';
import { Chart as ChartJS, CategoryScale, LinearScale, BarElement, Title } from 'chart.js';

ChartJS.register(CategoryScale, LinearScale, BarElement, Title);

function App() {
  const [query, setQuery] = useState('');
  const [location, setLocation] = useState('');
  const [jobs, setJobs] = useState([]);
  const [analysis, setAnalysis] = useState(null);

  const handleSearch = async () => {
    const response = await axios.post('http://127.0.0.1:5000/api/search', { query, location });
    setJobs(response.data.jobs);
    setAnalysis(response.data.analysis);
  };

  return (
    <div style={{ padding: '20px' }}>
      <h1>Live Job Tracker</h1>
      <input placeholder="Job Title" onChange={(e) => setQuery(e.target.value)} />
      <input placeholder="Location" onChange={(e) => setLocation(e.target.value)} />
      <button onClick={handleSearch}>Search</button>

      {jobs.length > 0 && (
        <div>
          <h2>Jobs Found</h2>
          {jobs.map((job, index) => (
            <div key={index} style={{ border: '1px solid #ccc', margin: '10px 0', padding: '10px' }}>
              <h3>{job.title}</h3>
              <p><strong>Company:</strong> {job.company}</p>
              <p><strong>Location:</strong> {job.location}</p>
            </div>
          ))}
        </div>
      )}

      {analysis && (
        <div style={{ maxWidth: '600px', marginTop: '20px' }}>
          <h2>Top Companies</h2>
          <Bar
            data={{
              labels: analysis.top_companies.map(item => item[0]),
              datasets: [{
                label: 'Job Count',
                data: analysis.top_companies.map(item => item[1]),
                backgroundColor: 'rgba(75, 192, 192, 0.6)'
              }]
            }}
          />
        </div>
      )}
    </div>
  );
}
export default App;
import { useState, setTimeout } from 'react'
import CodeMirror from '@uiw/react-codemirror'
// import 'codemirror/mode/python/python' // Ensure Python syntax mode is imported
import { python } from '@codemirror/lang-python'

import './App.css'

function App() {
  const [code, setCode] = useState('# Enter your Python code here')
  const [isRefactoring, setIsRefactoring] = useState(false)
  const [refactoredFunctions, setRefactoredFunctions] = useState([])
  const complexity_score =
    refactoredFunctions.length &&
    refactoredFunctions
      .map((f) => f.complexity_score)
      .reduce((a, b) => a + b, 0) / refactoredFunctions.length
  const readability_score =
    refactoredFunctions.length &&
    refactoredFunctions
      .map((f) => f.readability_score)
      .reduce((a, b) => a + b, 0) / refactoredFunctions.length

  const handleRefactorClick = () => {
    // Implement your refactor logic here
    setIsRefactoring(true) // Set loading state
    console.log(code)
    fetch(
      'https://simonmoisselin--refactor-code-v0-refactor-code-web.modal.run',
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ source_code: code })
      }
    )
      .then((res) => res.json())
      .then((data) => {
        setCode(data.reformated_code)
        setRefactoredFunctions(data.refactored_functions)
        setIsRefactoring(false) // Unset loading state
      })
      .catch((err) => {
        console.error('Error:', err)
        setIsRefactoring(false) // Unset loading state
      })

    console.log('Refactor clicked')
  }

  const handleCopyClick = () => {
    navigator.clipboard.writeText(code).then(
      () => {
        const copyButton = document.querySelector('.copy-btn')
        copyButton.classList.add('click-animate')

        // Remove the class after animation completes to reset the state
        setTimeout(() => {
          copyButton.classList.remove('click-animate')
        }, 300) // match the duration of the animation
      },

      (err) => {
        console.error('Could not copy code: ', err)
      }
    )
  }

  return (
    <div className="flex h-screen flex-col">
      <header className="bg-gray-800 p-4 text-2xl text-white">
        Code Refactoring: Python
      </header>
      <div className="flex grow overflow-hidden">
        <div className="w-4/5">
          <CodeMirror
            extensions={[python()]}
            value={code}
            onChange={(value) => {
              setCode(value)
            }}
            options={{
              mode: 'python',
              theme: 'material',
              lineNumbers: true,
              lineWrapping: true
              // wrap
            }}
            height="100%"
            className="size-full"
          />
        </div>
        <div className="flex w-1/5 flex-col items-center justify-start space-y-4 bg-gray-100 p-4">
          <button
            onClick={handleRefactorClick}
            className={`btn rounded bg-blue-500 px-4 py-2 font-bold text-white transition-colors duration-300 ease-in-out hover:bg-blue-700 ${
              isRefactoring ? 'animate-pulse' : ''
            }`}
            disabled={isRefactoring}
          >
            {isRefactoring ? 'Refactoring...' : 'Refactor'}
          </button>
          <button
            onClick={handleCopyClick}
            className="copy-btn btn rounded bg-green-500 px-4 py-2 font-bold text-white transition-colors duration-300 ease-in-out hover:bg-green-700"
          >
            Copy
          </button>
          <div className="flex flex-col items-center justify-start space-y-4 bg-gray-100 p-4">
            <h2 className="text-lg font-semibold">Refactoring Scores</h2>
            <div className="w-full text-center">
              <span className="font-medium">Complexity Score: </span>
              <span
                className={`font-semibold ${
                  complexity_score <= 0.5 ? 'text-green-600' : 'text-red-600'
                }`}
              >
                {complexity_score.toFixed(2)}
              </span>
            </div>
            <div className="w-full text-center">
              <span className="font-medium">Readability Score: </span>
              <span
                className={`font-semibold ${
                  readability_score >= 0.5 ? 'text-green-600' : 'text-red-600'
                }`}
              >
                {readability_score.toFixed(2)}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default App

// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-nocheck
import { useState, setTimeout } from 'react'
import CodeMirror from '@uiw/react-codemirror'
// import 'codemirror/mode/python/python' // Ensure Python syntax mode is imported
import { python } from '@codemirror/lang-python'

import './App.css'

const startCode = `def add(a, b):
  return a + b`

function App() {
  const [code, setCode] = useState(startCode)
  const [isRefactoring, setIsRefactoring] = useState(false)
  const [refactoringTime, setRefactoringTime] = useState(0)

  const [analysis, setAnalysis] = useState({
    reformated_code: '',
    functions: []
  })

  const handleRefactorClick = () => {
    setIsRefactoring(true) // Set loading state
    const startTime = performance.now() // Capture start time

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
        const endTime = performance.now() // Capture end time
        setRefactoringTime((endTime - startTime) / 1000) // Calculate duration in seconds
        setCode(data.reformated_code)
        setAnalysis(data)
        setIsRefactoring(false) // Unset loading state
      })
      .catch((err) => {
        console.error('Error:', err)
        setIsRefactoring(false) // Ensure refactoring time is set even on error
        const endTime = performance.now() // Capture end time on error
        setRefactoringTime((endTime - startTime) / 1000) // Calculate duration in seconds
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
            {isRefactoring ? 'Refactoring...' : 'Add Type Hinting'}
          </button>
          <button
            onClick={handleCopyClick}
            className="copy-btn btn rounded bg-green-500 px-4 py-2 font-bold text-white transition-colors duration-300 ease-in-out hover:bg-green-700"
          >
            Copy
          </button>
          {/* add a restart button */}
          <button
            onClick={() => setCode(startCode)}
            className="btn rounded bg-red-500 px-4 py-2 font-bold text-white transition-colors duration-300 ease-in-out hover:bg-red-700"
          >
            Restart
          </button>
          {refactoringTime ? (
            <p>Refactoring Time: {refactoringTime.toFixed(2)} seconds</p>
          ) : null}

          {analysis.functions.length ? (
            <div>
              {/* tailwind css */}
              <h2
                className="
                text-2xl
                font-bold
                text-gray-800
              "
              >
                Functions
              </h2>
              <ul
                className="
                text-gray-700 
              "
              >
                {analysis.functions.map((func: any) => (
                  <li
                    className="
                      ml-4
                      list-disc
                      text-gray-700
                    "
                    key={func.name}
                  >
                    {func.name}({func.args.join(', ')})
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  )
}

export default App

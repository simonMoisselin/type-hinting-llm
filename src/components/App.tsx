// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-nocheck
import { useState, setTimeout } from 'react'
import CodeMirror from '@uiw/react-codemirror'
// import 'codemirror/mode/python/python' // Ensure Python syntax mode is imported
import { python } from '@codemirror/lang-python'

import './App.css'

const startCode = `import pandas as pd
import numpy as np
from tensorflow import keras
from tensorflow.keras import layers
from keras.datasets import mnist
from keras.utils import np_utils

def load_data():
    (x_train, y_train), (x_test, y_test) = mnist.load_data()
    return x_train, y_train, x_test, y_test

def preprocess_data(x_train, x_test):
    x_train = x_train.reshape(x_train.shape[0], 28, 28, 1).astype('float32') / 255
    x_test = x_test.reshape(x_test.shape[0], 28, 28, 1).astype('float32') / 255
    return x_train, x_test

def encode_labels(y_train, y_test):
    y_train = np_utils.to_categorical(y_train, 10)
    y_test = np_utils.to_categorical(y_test, 10)
    return y_train, y_test

def create_model():
    model = keras.Sequential([
        layers.Conv2D(32, kernel_size=(3, 3), activation='relu', input_shape=(28, 28, 1)),
        layers.MaxPooling2D(pool_size=(2, 2)),
        layers.Conv2D(64, (3, 3), activation='relu'),
        layers.MaxPooling2D(pool_size=(2, 2)),
        layers.Flatten(),
        layers.Dense(128, activation='relu'),
        layers.Dense(10, activation='softmax')
    ])
    model.compile(optimizer='adam', loss='categorical_crossentropy', metrics=['accuracy'])
    return model

def train_model(model, x_train, y_train, x_test, y_test):
    model.fit(x_train, y_train, batch_size=128, epochs=10, verbose=1, validation_data=(x_test, y_test))

def evaluate_model(model, x_test, y_test):
    score = model.evaluate(x_test, y_test, verbose=0)
    print('Test loss:', score[0])
    print('Test accuracy:', score[1])`

const MODELS = {
  GPT3: 'gpt-3.5-turbo-0125',
  GPT4: 'gpt-4-0125-preview'
}
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
      'https://simonmoisselin--refactor-code-v1-refactor-code-web.modal.run',
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ source_code: code, model_name: MODELS.GPT3 })
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
        <div className="w-3/5">
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
        <div className="flex w-2/5 flex-col items-center justify-start space-y-4 bg-gray-100 p-4">
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
          <h2
            className="
                text-2xl
                font-bold
                text-gray-800
              "
          >
            Functions Modified
          </h2>
          {analysis.functions.length ? (
            <div
              className="
                max-h-96
                w-full
                overflow-y-auto
                rounded
                bg-gray-200
                p-4
                text-lg
                text-gray-800
            "
            >
              {/* tailwind css */}
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
                    {func.name}({func.args?.join(', ')})
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

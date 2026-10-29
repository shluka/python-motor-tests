// ============================================================
// MOTOR TEST BENCH - PROGRAMMABLE CYCLIC PROTOCOL
//
// Available serial commands:
//
// CLEAR
//
// BLOCK,cycles,distance_mm,forward_speed_mm_s,
//       hold_max_s,backward_speed_mm_s,
//       hold_zero_s,hold_after_block_s
//
// RUN
//
// STOP
//
// Example:
//
// CLEAR
// BLOCK,3,5,1,0,1,0,10
// BLOCK,5,10,1,0,1,0,0
// RUN
//
// This protocol performs:
//
// Block 1:
//   3 cycles from 0 to 5 mm
//   Forward speed:  1 mm/s
//   Hold at 5 mm:   0 s
//   Backward speed: 1 mm/s
//   Hold at 0 mm:   0 s
//   Final hold:     10 s
//
// Block 2:
//   5 cycles from 0 to 10 mm
//   No final hold
// ============================================================


// ============================================================
// MOTOR PINS
// ============================================================

const int DIR_PIN  = 2;
const int STEP_PIN = 3;


// ============================================================
// SERIAL COMMUNICATION
// ============================================================

const unsigned long BAUD_RATE = 9600;


// ============================================================
// MECHANICAL CONFIGURATION
// ============================================================

// Motor steps per revolution, including microstepping.
const long STEPS_PER_REV = 3200;

// Linear displacement produced by one spindle revolution.
const float MM_PER_REV = 2.0;

// Number of motor steps required for 1 mm of displacement.
const float STEPS_PER_MM =
  static_cast<float>(STEPS_PER_REV) / MM_PER_REV;


// ============================================================
// PROTOCOL CONFIGURATION
// ============================================================

// Maximum number of blocks stored in the Arduino UNO.
//
// The UNO has limited RAM, so this value should not be made
// unnecessarily large.
const int MAX_BLOCKS = 10;


// Structure containing the parameters of one protocol block.
struct TestBlock
{
  int cycles;

  float distance_mm;

  float forwardSpeed_mm_s;
  float backwardSpeed_mm_s;

  unsigned long holdMaximum_ms;
  unsigned long holdZero_ms;
  unsigned long holdAfterBlock_ms;
};


// Array containing all configured blocks.
TestBlock protocolBlocks[MAX_BLOCKS];

// Number of currently stored blocks.
int numberOfBlocks = 0;


// ============================================================
// EXECUTION STATE
// ============================================================

bool protocolRunning = false;
bool stopRequested = false;


// ============================================================
// SETUP
// ============================================================

void setup()
{
  pinMode(DIR_PIN, OUTPUT);
  pinMode(STEP_PIN, OUTPUT);

  digitalWrite(DIR_PIN, LOW);
  digitalWrite(STEP_PIN, LOW);

  Serial.begin(BAUD_RATE);
  Serial.setTimeout(100);

  delay(2000);

  Serial.println("READY");
}


// ============================================================
// MAIN LOOP
// ============================================================

void loop()
{
  if (Serial.available() <= 0)
  {
    return;
  }

  String command = Serial.readStringUntil('\n');
  command.trim();

  if (command.length() == 0)
  {
    return;
  }

  processCommand(command);
}


// ============================================================
// PROCESS SERIAL COMMAND
// ============================================================

void processCommand(const String &command)
{
  // ----------------------------------------------------------
  // EMERGENCY STOP
  // ----------------------------------------------------------

  if (command == "STOP")
  {
    stopRequested = true;

    if (!protocolRunning)
    {
      Serial.println("STOPPED");
      Serial.println("READY");
    }

    return;
  }


  // ----------------------------------------------------------
  // CLEAR STORED PROTOCOL
  // ----------------------------------------------------------

  if (command == "CLEAR")
  {
    if (protocolRunning)
    {
      Serial.println("ERROR,PROTOCOL_RUNNING");
      return;
    }

    clearProtocol();

    Serial.println("OK,CLEAR");
    Serial.println("READY");

    return;
  }


  // ----------------------------------------------------------
  // ADD A NEW BLOCK
  // ----------------------------------------------------------

  if (command.startsWith("BLOCK,"))
  {
    if (protocolRunning)
    {
      Serial.println("ERROR,PROTOCOL_RUNNING");
      return;
    }

    TestBlock newBlock;

    if (!parseBlockCommand(command, newBlock))
    {
      Serial.println("ERROR,INVALID_BLOCK");
      Serial.println("READY");
      return;
    }

    if (numberOfBlocks >= MAX_BLOCKS)
    {
      Serial.println("ERROR,MAX_BLOCKS_REACHED");
      Serial.println("READY");
      return;
    }

    protocolBlocks[numberOfBlocks] = newBlock;
    numberOfBlocks++;

    Serial.print("OK,BLOCK,");
    Serial.println(numberOfBlocks);

    printBlockConfiguration(
      numberOfBlocks,
      protocolBlocks[numberOfBlocks - 1]);

    Serial.println("READY");

    return;
  }


  // ----------------------------------------------------------
  // RUN STORED PROTOCOL
  // ----------------------------------------------------------

  if (command == "RUN")
  {
    if (protocolRunning)
    {
      Serial.println("ERROR,PROTOCOL_RUNNING");
      return;
    }

    if (numberOfBlocks == 0)
    {
      Serial.println("ERROR,NO_BLOCKS");
      Serial.println("READY");
      return;
    }

    stopRequested = false;
    protocolRunning = true;

    Serial.print("OK,RUN,");
    Serial.println(numberOfBlocks);

    runProtocol();

    protocolRunning = false;

    Serial.println("READY");

    return;
  }


  // ----------------------------------------------------------
  // UNKNOWN COMMAND
  // ----------------------------------------------------------

  Serial.println("ERROR,INVALID_COMMAND");
  Serial.println("READY");
}


// ============================================================
// CLEAR PROTOCOL
// ============================================================

void clearProtocol()
{
  numberOfBlocks = 0;
  stopRequested = false;
}


// ============================================================
// PARSE BLOCK COMMAND
// ============================================================

bool parseBlockCommand(
  const String &command,
  TestBlock &block)
{
  /*
    Expected format:

    BLOCK,
    cycles,
    distance_mm,
    forward_speed_mm_s,
    hold_max_s,
    backward_speed_mm_s,
    hold_zero_s,
    hold_after_block_s

    Example:

    BLOCK,3,5,1,0,1,0,10
  */

  const int NUMBER_OF_FIELDS = 8;

  String fields[NUMBER_OF_FIELDS];

  int fieldIndex = 0;
  int startIndex = 0;

  for (int characterIndex = 0;
       characterIndex <= command.length();
       characterIndex++)
  {
    bool endOfField =
      characterIndex == command.length() ||
      command.charAt(characterIndex) == ',';

    if (endOfField)
    {
      if (fieldIndex >= NUMBER_OF_FIELDS)
      {
        return false;
      }

      fields[fieldIndex] =
        command.substring(startIndex, characterIndex);

      fields[fieldIndex].trim();

      fieldIndex++;
      startIndex = characterIndex + 1;
    }
  }

  if (fieldIndex != NUMBER_OF_FIELDS)
  {
    return false;
  }

  if (fields[0] != "BLOCK")
  {
    return false;
  }

  int cycles =
    fields[1].toInt();

  float distance_mm =
    fields[2].toFloat();

  float forwardSpeed_mm_s =
    fields[3].toFloat();

  float holdMaximum_s =
    fields[4].toFloat();

  float backwardSpeed_mm_s =
    fields[5].toFloat();

  float holdZero_s =
    fields[6].toFloat();

  float holdAfterBlock_s =
    fields[7].toFloat();


  // ----------------------------------------------------------
  // PARAMETER VALIDATION
  // ----------------------------------------------------------

  if (cycles < 1)
  {
    return false;
  }

  if (distance_mm <= 0.0)
  {
    return false;
  }

  if (forwardSpeed_mm_s <= 0.0)
  {
    return false;
  }

  if (backwardSpeed_mm_s <= 0.0)
  {
    return false;
  }

  if (holdMaximum_s < 0.0)
  {
    return false;
  }

  if (holdZero_s < 0.0)
  {
    return false;
  }

  if (holdAfterBlock_s < 0.0)
  {
    return false;
  }


  // ----------------------------------------------------------
  // STORE PARSED VALUES
  // ----------------------------------------------------------

  block.cycles = cycles;

  block.distance_mm = distance_mm;

  block.forwardSpeed_mm_s =
    forwardSpeed_mm_s;

  block.backwardSpeed_mm_s =
    backwardSpeed_mm_s;

  block.holdMaximum_ms =
    secondsToMilliseconds(holdMaximum_s);

  block.holdZero_ms =
    secondsToMilliseconds(holdZero_s);

  block.holdAfterBlock_ms =
    secondsToMilliseconds(holdAfterBlock_s);

  return true;
}


// ============================================================
// CONVERT SECONDS TO MILLISECONDS
// ============================================================

unsigned long secondsToMilliseconds(float seconds)
{
  return static_cast<unsigned long>(
    lround(seconds * 1000.0));
}


// ============================================================
// RUN COMPLETE PROTOCOL
// ============================================================

void runProtocol()
{
  Serial.print("START_PROTOCOL,");
  Serial.println(numberOfBlocks);

  for (int blockIndex = 0;
       blockIndex < numberOfBlocks;
       blockIndex++)
  {
    if (stopRequested)
    {
      Serial.println("ABORTED");
      return;
    }

    int displayedBlockNumber = blockIndex + 1;

    TestBlock &currentBlock =
      protocolBlocks[blockIndex];

    bool completed =
      runBlock(
        currentBlock,
        displayedBlockNumber);

    if (!completed)
    {
      Serial.println("ABORTED");
      return;
    }
  }

  Serial.println("FIN");
}


// ============================================================
// RUN ONE PROTOCOL BLOCK
// ============================================================

bool runBlock(
  const TestBlock &block,
  int blockNumber)
{
  long numberOfSteps =
    lround(block.distance_mm * STEPS_PER_MM);

  unsigned long forwardPulseDelay_us =
    calculatePulseDelay(
      block.forwardSpeed_mm_s);

  unsigned long backwardPulseDelay_us =
    calculatePulseDelay(
      block.backwardSpeed_mm_s);


  // ----------------------------------------------------------
  // BLOCK START
  // ----------------------------------------------------------

  Serial.print("START_BLOCK,");
  Serial.println(blockNumber);

  printBlockConfiguration(
    blockNumber,
    block);


  // ----------------------------------------------------------
  // EXECUTE ALL CYCLES
  // ----------------------------------------------------------

  for (int cycle = 1;
       cycle <= block.cycles;
       cycle++)
  {
    if (stopRequested)
    {
      return false;
    }


    // --------------------------------------------------------
    // FORWARD RAMP
    // --------------------------------------------------------

    Serial.print("START_FORWARD,");
    Serial.print(blockNumber);
    Serial.print(",");
    Serial.println(cycle);

    bool completed =
      moveMotor(
        HIGH,
        numberOfSteps,
        forwardPulseDelay_us);

    if (!completed)
    {
      return false;
    }

    Serial.print("END_FORWARD,");
    Serial.print(blockNumber);
    Serial.print(",");
    Serial.println(cycle);


    // --------------------------------------------------------
    // HOLD AT MAXIMUM DISPLACEMENT
    // --------------------------------------------------------

    Serial.print("START_HOLD_MAX,");
    Serial.print(blockNumber);
    Serial.print(",");
    Serial.print(cycle);
    Serial.print(",");
    Serial.println(block.holdMaximum_ms);

    if (!controlledDelay(block.holdMaximum_ms))
    {
      return false;
    }

    Serial.print("END_HOLD_MAX,");
    Serial.print(blockNumber);
    Serial.print(",");
    Serial.println(cycle);


    // --------------------------------------------------------
    // BACKWARD RAMP
    // --------------------------------------------------------

    Serial.print("START_BACKWARD,");
    Serial.print(blockNumber);
    Serial.print(",");
    Serial.println(cycle);

    completed =
      moveMotor(
        LOW,
        numberOfSteps,
        backwardPulseDelay_us);

    if (!completed)
    {
      return false;
    }

    Serial.print("END_BACKWARD,");
    Serial.print(blockNumber);
    Serial.print(",");
    Serial.println(cycle);


    // --------------------------------------------------------
    // HOLD AT ZERO DISPLACEMENT
    // --------------------------------------------------------

    Serial.print("START_HOLD_ZERO,");
    Serial.print(blockNumber);
    Serial.print(",");
    Serial.print(cycle);
    Serial.print(",");
    Serial.println(block.holdZero_ms);

    if (!controlledDelay(block.holdZero_ms))
    {
      return false;
    }

    Serial.print("END_HOLD_ZERO,");
    Serial.print(blockNumber);
    Serial.print(",");
    Serial.println(cycle);


    // --------------------------------------------------------
    // CYCLE END
    // --------------------------------------------------------

    Serial.print("END_CYCLE,");
    Serial.print(blockNumber);
    Serial.print(",");
    Serial.println(cycle);
  }


  // ----------------------------------------------------------
  // HOLD AFTER BLOCK
  // ----------------------------------------------------------

  Serial.print("START_BLOCK_HOLD,");
  Serial.print(blockNumber);
  Serial.print(",");
  Serial.println(block.holdAfterBlock_ms);

  if (!controlledDelay(block.holdAfterBlock_ms))
  {
    return false;
  }

  Serial.print("END_BLOCK_HOLD,");
  Serial.println(blockNumber);


  // ----------------------------------------------------------
  // BLOCK END
  // ----------------------------------------------------------

  Serial.print("END_BLOCK,");
  Serial.println(blockNumber);

  return true;
}


// ============================================================
// PRINT BLOCK CONFIGURATION
// ============================================================

void printBlockConfiguration(
  int blockNumber,
  const TestBlock &block)
{
  Serial.print("CONFIG_BLOCK,");
  Serial.print(blockNumber);
  Serial.print(",");

  Serial.print(block.cycles);
  Serial.print(",");

  Serial.print(block.distance_mm, 4);
  Serial.print(",");

  Serial.print(block.forwardSpeed_mm_s, 4);
  Serial.print(",");

  Serial.print(block.holdMaximum_ms);
  Serial.print(",");

  Serial.print(block.backwardSpeed_mm_s, 4);
  Serial.print(",");

  Serial.print(block.holdZero_ms);
  Serial.print(",");

  Serial.println(block.holdAfterBlock_ms);
}


// ============================================================
// CALCULATE STEP-PULSE DELAY
// ============================================================

unsigned long calculatePulseDelay(
  float speed_mm_s)
{
  float stepFrequency =
    speed_mm_s * STEPS_PER_MM;

  unsigned long pulseDelay_us =
    lround(
      1000000.0 /
      (2.0 * stepFrequency));

  // Minimum safe pulse duration for the driver.
  if (pulseDelay_us < 2)
  {
    pulseDelay_us = 2;
  }

  return pulseDelay_us;
}


// ============================================================
// MOTOR MOVEMENT
// ============================================================

bool moveMotor(
  int direction,
  long numberOfSteps,
  unsigned long pulseDelay_us)
{
  digitalWrite(DIR_PIN, direction);

  delayMicroseconds(10);

  for (long stepIndex = 0;
       stepIndex < numberOfSteps;
       stepIndex++)
  {
    /*
      Check the serial port every 100 steps.

      This allows STOP to interrupt the movement without checking
      the serial port during every motor pulse.
    */

    if ((stepIndex % 100) == 0)
    {
      checkStopCommand();

      if (stopRequested)
      {
        digitalWrite(STEP_PIN, LOW);
        return false;
      }
    }

    digitalWrite(STEP_PIN, HIGH);
    delayMicroseconds(pulseDelay_us);

    digitalWrite(STEP_PIN, LOW);
    delayMicroseconds(pulseDelay_us);
  }

  digitalWrite(STEP_PIN, LOW);

  return true;
}


// ============================================================
// CONTROLLED HOLD
// ============================================================

bool controlledDelay(unsigned long duration_ms)
{
  if (duration_ms == 0)
  {
    checkStopCommand();
    return !stopRequested;
  }

  unsigned long startTime = millis();

  while ((millis() - startTime) < duration_ms)
  {
    checkStopCommand();

    if (stopRequested)
    {
      return false;
    }

    delay(5);
  }

  return true;
}


// ============================================================
// CHECK FOR STOP COMMAND
// ============================================================

void checkStopCommand()
{
  if (Serial.available() <= 0)
  {
    return;
  }

  String message = Serial.readStringUntil('\n');
  message.trim();

  if (message == "STOP")
  {
    stopRequested = true;
  }
}
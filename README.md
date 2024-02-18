# GridAPPS-D IEEE 2030.5 Server
## Forked from: https://pypi.org/project/gridappsd-2030-5/

## Overview

The GridAPPS-D IEEE 2030.5 Server implements the Common Smart Inverter Profile (CSIP).  The server
can work in both in-band and out-of-band registration models detailed in  CCIP Implementation Guide v2
section 6.1.3 and 6.1.4 respectively.  

## Setup

## Installing from pypi

The recommended way to install this project from pypi is in a virtual environment.  Create a virtual environment and install
2030.5 server as follows.

```shell
# creates an environment 'env' in the current directory
python3 -m venv env

# Activate the environment in the current shell
source env/bin/activate

# Install 2030.5 server
pip install gridappsd_2030_5
```

## Configuration

The server requires two configuration files.  The first is for generation of certificates and keys for the system (openssl.cnf).  Currently
we shell out to openssl for key/cert/ca generation during runtime.  Each time the server is started up it will attempt to regenerate
key/certs/ca unless --no-create-certs is passed to the server startup method.  The second is the configuration for the server itself.  
The configuration file holds the definitions for controls, der, end devices and other settings that will be used during the runtime
of the server.

The following files, openssl.cnf and config.yml, should be placed in the same directory where the server is started from.

### Example openssl.cnf

```ini
# OpenSSL example configuration file.
# This is mostly being used for generation of certificate requests.
#

# This definition stops the following lines choking if HOME isn't
# defined.
HOME                    = .
RANDFILE                = $ENV::HOME/.rnd

# Extra OBJECT IDENTIFIER info:
#oid_file               = $ENV::HOME/.oid
oid_section             = new_oids

# To use this configuration file with the "-extfile" option of the
# "openssl x509" utility, name here the section containing the
# X.509v3 extensions to use:
# extensions            =
# (Alternatively, use a configuration file that has only
# X.509v3 extensions in its main [= default] section.)

[ new_oids ]

# We can add new OIDs in here for use by 'ca', 'req' and 'ts'.
# Add a simple OID like this:
# testoid1=1.2.3.4
# Or use config file substitution like this:
# testoid2=${testoid1}.5.6

# Policies used by the TSA examples.
tsa_policy1 = 1.2.3.4.1
tsa_policy2 = 1.2.3.4.5.6
tsa_policy3 = 1.2.3.4.5.7

####################################################################
[ ca ]
default_ca      = CA_default            # The default ca section

[ CA_default ]
dir             = $ENV::HOME/tls             # Where everything is kept
certs           = $dir/certs            # Where the issued certs are kept
database        = $dir/index.txt        # database index file.
                                        # several certs with same subject.
new_certs_dir   = $dir/certs            # default place for new certs.
certificate     = $dir/certs/ec-cacert.pem       # The CA certificate
serial          = $dir/serial           # The current serial number
crlnumber       = $dir/crlnumber        # the current crl number
                                        # must be commented out to leave a V1 CRL
private_key     = $dir/private/ec-cakey.pem # The private key

name_opt        = ca_default            # Subject Name options
cert_opt        = ca_default            # Certificate field options

default_days    = 365                   # how long to certify for
default_crl_days= 30                    # how long before next CRL
default_md      = sha256                # use SHA-256 by default
preserve        = no                    # keep passed DN ordering
policy          = policy_match

# For the CA policy
[ policy_match ]
countryName             = optional
stateOrProvinceName     = optional
organizationName        = optional
organizationalUnitName  = optional
commonName              = supplied
emailAddress            = optional

[ policy_anything ]
countryName             = optional
stateOrProvinceName     = optional
localityName            = optional
organizationName        = optional
organizationalUnitName  = optional
commonName              = supplied
emailAddress            = optional

####################################################################
[ req ]
default_bits            = 2048
default_md              = sha256
default_keyfile         = privkey.pem
distinguished_name      = req_distinguished_name
attributes              = req_attributes
x509_extensions = v3_ca # The extentions to add to the self signed cert

[ req_distinguished_name ]
countryName                     = Country Name (2 letter code)
countryName_default             = IN
countryName_min                 = 2
countryName_max                 = 2
stateOrProvinceName             = State or Province Name (full name)
stateOrProvinceName_default     = Some-State
localityName                    = Locality Name (eg, city)
localityName_default            = BANGALORE
0.organizationName              = Organization Name (eg, company)
0.organizationName_default      = GoLinuxCloud
organizationalUnitName          = Organizational Unit Name (eg, section)
commonName                      = Common Name (eg, your name or your server\'s hostname)
commonName_max                  = 64
emailAddress                    = Email Address
emailAddress_max                = 64

[ req_attributes ]
challengePassword               = A challenge password
challengePassword_min           = 4
challengePassword_max           = 20
unstructuredName                = An optional company name


[ v3_req ]
# Extensions to add to a certificate request
basicConstraints = CA:FALSE
keyUsage = nonRepudiation, digitalSignature, keyEncipherment

[ v3_ca ]
# Extensions for a typical CA
subjectKeyIdentifier=hash
authorityKeyIdentifier=keyid:always,issuer
basicConstraints = critical,CA:true

[ crl_ext ]
# issuerAltName=issuer:copy
authorityKeyIdentifier=keyid:always
```

```yaml

### Example config.yml
---
#server_hostname: 0.0.0.0:8443

server: 127.0.0.1
# Only include if we need to have dcap be available
# http_port: 8080
https_port: 7443

proxy_hostname: 0.0.0.0:8443
#server_hostname: 0.0.0.0:7443
# server_hostname: gridappsd_dev_2004:7443

tls_repository: "./tls"
openssl_cnf: "openssl.cnf"

#server_mode: enddevices_register_access_only
server_mode: enddevices_create_on_start

# lfdi_mode: Determines what piece of information is used to calculate the lfdi
#
# Options:
#   lfdi_mode_from_file             - sha256 hash of certificate file's content.
#   lfdi_mode_from_cert_fingerprint - sha256 hash of the certificates fingerprint.
#
# default: lfdi_mode_from_cert_fingerprint
#lfdi_mode: lfdi_mode_from_file
lfdi_mode: lfdi_mode_from_cert_fingerprint

# Create an administrator certificate that can be used from
# browser/api to connect to the platform.
generate_admin_cert: True

log_event_list_poll_rate: 60
device_capability_poll_rate: 60

# End Device
devices:
  # SolarEdge SE6000H HD-Wave SetApp Enabled Inverter
  - id: dev1
    # DeviceCategoryType from ieee_2030_5.models.device_category
    deviceCategory: FUEL_CELL
    pin: 111115

    programs:
      - description: Program 1

    # nameplate:
    #   rtgMaxW: 6000
    ders:
      - capabilities:
        modesSupported: "1110000000000000"
        type: 83

      - capabilities:
        # Bitmask with the following structure.
        # Indication of support for each control mode function DERCapability::modesSupported
        #
        # 0 - Charge mode
        # 1 - Discharge mode
        # 2 - opModConnect (Connect / Disconnect -
        # implies galvanic isolation)
        # 3 - opModEnergize (Energize / De-Energize)
        # 4 - opModFixedPFAbsorbW (Fixed Power
        # Factor Setpoint when absorbing active
        # power)
        # 5 - opModFixedPFInjectW (Fixed Power
        # Factor Setpoint when injecting active
        # power)
        # 6 - opModFixedVar (Reactive Power
        # Setpoint)
        # 7 - opModFixedW (Charge / Discharge
        # Setpoint)
        # 8 - opModFreqDroop (Frequency-Watt
        # Parameterized Mode)
        # 9 - opModFreqWatt (Frequency-Watt
        # Curve Mode)
        # 10 - opModHFRTMayTrip (High Frequency
        # Ride Through, May Trip Mode)
        # 11 - opModHFRTMustTrip (High
        # Frequency Ride Through, Must Trip Mode)
        # 12 - opModHVRTMayTrip (High Voltage
        # Ride Through, May Trip Mode)
        # 13 - opModHVRTMomentaryCessation
        # (High Voltage Ride Through, Momentary
        # Cessation Mode)
        # 14 - opModHVRTMustTrip (High Voltage
        # Ride Through, Must Trip Mode)
        # 15 - opModLFRTMayTrip (Low Frequency
        # Ride Throu
        modesSupported: "1110000000000000"

        # Item type for the DER.
        # 0 - Not applicable / Unknown
        # 1 - Virtual or mixed DER
        # 2 - Reciprocating engine
        # 3 - Fuel cell
        # 4 - Photovoltaic system
        # 5 - Combined heat and power
        # 6 - Other generation system
        # 80 - Other storage system
        # 81 - Electric vehicle
        # 82 - EVSE
        # 83 - Combined PV and storage
        type: 83

        # Default available nameplate options where at a manufacturer's set.
        # Active power rating in watts an unity power factor
        rtgMaxW: 600

        # Active power rating in watts at specified over-excited power factor
        # rtgOverExcitedW:

        # Over-excited power factor DERCapability::rtgOverExcitedPF
        # rtgOverExcitedPF:

        # Active power rating in watts at specified under-excited power factor DERCapability::rtgUnderExcitedW
        # rtgUnderExcitedW:

        # Under-excited power factor DERCapability::rtgUnderExcitedPF
        # rtgUnderExcitedPF:

        # Maximum apparent power rating in voltamperes DERCapability::rtgMaxVA
        rtgMaxVA: 600

        # Indication of reactive power and voltage/power control capability DERCapability::rtgNormalCategory
        rtgNormalCategory: 1

        # Indication of voltage and frequencyride-through capability category I, II, or III DERCapability::rtgAbnormalCategory
        rtgAbnormalCategory: 1

        # Maximum injected reactive power rating in vars DERCapability::rtgMaxVar
        rtgMaxVar: 600

        # Maximum absorbed reactive power rating in vars DERCapability::rtgMaxVarNeg
        rtgMaxVarNeg: 600

        # Maximum active power charge rating in watts DERCapability::rtgMaxChargeRateW
        rtgMaxChargeRateW: 600

        # Maximum apparent power charge rating in voltamperes; may differ from the apparent power maximum rating
        # DERCapability::rtgMaxChargeRateVA
        rtgMaxChargeRateVA: 600

        # Nominal ac voltage rating in rms volts DERCapability::rtgVNom
        rtgVNom: 120

        # Maximum ac voltage rating in rms volts DERCapability::rtgMaxV
        rtgMaxV: 128

        # Minimum ac voltage rating in rms volts DERCapability::rtgMinV
        rtgMinV: 116

        # Reactive susceptance that remains connected to the Area EPS in the cease to energize and trip state
        # DERCapability::rtgReactiveSusceptance
        # rtgReactiveSusceptance:

        # # Manufacturer DeviceInformation::mfID
        # mfID:

        # # Model DeviceInformation::mfModel
        # mfModel:

        # # Serial number DeviceInformation::mfSerNum
        # mfSerNum:

        # # Version DeviceInformation::mfHwVer DeviceInformation::swVer
        # mfHwVer:
        # swVer:

  - id: dev2
    deviceCategory: FUEL_CELL
    pin: 12345
    nameplate:

programs:
  - description: Program 1
    default_control: Control 1
    controls:
      - Control 2
      - Control 3
    curves:
      - Curve 1
    primacy: 89

controls:
  - description: Control 1
    setESDelay: 30
    base:
      opModConnect: True
      opModMaxLimW: 9500

      # setESHighFreq: UInt16 [0..1]
      # setESHighVolt: Int16 [0..1]
      # setESLowFreq: UInt16 [0..1]
      # setESLowVolt: Int16 [0..1]
      # setESRampTms: UInt32 [0..1]
      # setESRandomDelay: UInt32 [0..1]
      # setGradW: UInt16 [0..1]
      # setSoftGradW: UInt16 [0..1]
  - description: Control 2
  - description: Control 3

events:
  - control: 0

curves:
  # Each element will can have the following structure.
  # autonomousVRefEnable: If the curveType is opModVoltVar, then
  #   this field MAY be present. If the curveType is not opModVoltVar,
  #   then this field SHALL NOT be present. Enable/disable autonomous
  #   vRef adjustment. When enabled, the Volt-Var curve characteristic
  #   SHALL be adjusted autonomously as vRef changes and
  #   autonomousVRefTimeConstant SHALL be present. If a DER is able to
  #   support Volt-Var mode but is unable to support autonomous vRef
  #   adjustment, then the DER SHALL execute the curve without
  #   autonomous vRef adjustment. If not specified, then the value is
  #   false.
  # autonomousVRefTimeConstant: If the curveType is opModVoltVar,
  #   then this field MAY be present. If the curveType is not
  #   opModVoltVar, then this field SHALL NOT be present. Adjustment
  #   range for vRef time constant, in hundredths of a second.
  # creationTime: The time at which the object was created.
  # CurveData:
  # curveType: Specifies the associated curve-based control mode.
  # openLoopTms: Open loop response time, the time to ramp up to
  #   90% of the new target in response to the change in voltage, in
  #   hundredths of a second. Resolution is 1/100 sec. A value of 0 is
  #   used to mean no limit. When not present, the device SHOULD
  #   follow its default behavior.
  # rampDecTms: Decreasing ramp rate, interpreted as a percentage
  #   change in output capability limit per second (e.g. %setMaxW /
  #   sec).  Resolution is in hundredths of a percent/second. A value
  #   of 0 means there is no limit. If absent, ramp rate defaults to
  #   setGradW.
  # rampIncTms: Increasing ramp rate, interpreted as a percentage
  #   change in output capability limit per second (e.g. %setMaxW /
  #   sec).  Resolution is in hundredths of a percent/second. A value
  #   of 0 means there is no limit. If absent, ramp rate defaults to
  #   rampDecTms.
  # rampPT1Tms: The configuration parameter for a low-pass filter,
  #   PT1 is a time, in hundredths of a second, in which the filter
  #   will settle to 95% of a step change in the input value.
  #   Resolution is 1/100 sec.
  # vRef: If the curveType is opModVoltVar, then this field MAY be
  #   present. If the curveType is not opModVoltVar, then this field
  #   SHALL NOT be present. The nominal AC voltage (RMS) adjustment to
  #   the voltage curve points for Volt-Var curves.
  # xMultiplier: Exponent for X-axis value.
  # yMultiplier: Exponent for Y-axis value.
  # yRefType: The Y-axis units context.
  # Each curve MUST have between 1 and 10 elements in the curve_data list.
  #
  # DERCurve Type for each curve.
  # 0 - opModFreqWatt (Frequency-Watt Curve Mode)
  # 1 - opModHFRTMayTrip (High Frequency Ride Through, May Trip Mode)
  # 2 - opModHFRTMustTrip (High Frequency Ride Through, Must Trip Mode)
  # 3 - opModHVRTMayTrip (High Voltage Ride Through, May Trip Mode)
  # 4 - opModHVRTMomentaryCessation (High Voltage Ride Through, Momentary Cessation
  # Mode)
  # 5 - opModHVRTMustTrip (High Voltage Ride Through, Must Trip Mode)
  # 6 - opModLFRTMayTrip (Low Frequency Ride Through, May Trip Mode)
  # 7 - opModLFRTMustTrip (Low Frequency Ride Through, Must Trip Mode)
  # 8 - opModLVRTMayTrip (Low Voltage Ride Through, May Trip Mode)
  # 9 - opModLVRTMomentaryCessation (Low Voltage Ride Through, Momentary Cessation
  # Mode)
  # 10 - opModLVRTMustTrip (Low Voltage Ride Through, Must Trip Mode)
  # 11 - opModVoltVar (Volt-Var Mode)
  # 12 - opModVoltWatt (Volt-Watt Mode)
  # 13 - opModWattPF (Watt-PowerFactor Mode)
  # 14 - opModWattVar (Watt-Var Mode)
  - description: Curve 1
    curveType: opModVoltVar
    CurveData:
      - xvalue: 5
        yvalue: 5

  - description: Curve 2
    curveType: opModFreqWatt
    CurveData:
      # exitation is only available if yvalue is power factor
      - exitation: 10
        xvalue: 5
        yvalue: 5
```

### Starting the server

After installing one can start the server by the folloing command:

```bash
2030_5_server --no-validate config.yml
```

To learn about other options please use the help module.

```bash
2030_5_server --help
```

## Installing from source

The installation requires poetry version 1.2 or greater.  <https://python-poetry.org/docs/#installation>

 1. Clone the repository
 2. run `poetry install` from the root of the repository directory.

### Clone the repository

```shell
git clone https://github.com/GRIDAPPSD/gridappsd-2030_5 -b develop
cd gridappsd-2030_5
```

### Install Requirements

```shell
poetry install
```

### Run the Server

```shell
usage: 2030_5_server [-h] [--no-validate] [--no-create-certs] [--debug] config

positional arguments:
  config             Configuration file for the server.

optional arguments:
  -h, --help         show this help message and exit
  --no-validate      Allows faster startup since the resolving of addresses for devices is not done.
  --no-create-certs  If specified certificates for for client and server will not be created.
  --debug            Put server in debug mode (more logging)
```

### Using the 2030.5 proxy

The proxy is used to keep a http 1.1 connection alive rather than doing the tls setup
more than one time.

```shell
usage: 2030_5_proxy [-h] [--debug] config

positional arguments:
  config      Configuration file for the server.

optional arguments:
  -h, --help  show this help message and exit
  --debug     Turns debugging on for logging of the proxy.
```

## Client Connectivity

The server will expose an endpoint of beginning with <https://myserver/dcap>.  From there
a client will be able to traverse and do any PUT, POST, GET, and DELETE operations specified
in the 2030.5 test procedures.

## Function Sets Implemented

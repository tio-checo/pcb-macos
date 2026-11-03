;;; PCB forward annotation backend for Lepton EDA.
;;; SPDX-License-Identifier: GPL-2.0-or-later

(define-module (backend pcbfwd)
  #:use-module (ice-9 format)
  #:use-module (rnrs bytevectors)
  #:use-module (netlist)
  #:use-module (netlist schematic)
  #:use-module (netlist schematic toplevel)
  #:export (pcbfwd))

;; PCB's action parser understands double-quoted arguments and backslash
;; escapes. Literal line breaks would become separate actions.
(define (quote-argument value)
  (string-append
   "\""
   (string-concatenate
    (map (lambda (ch)
           (cond ((memv ch '(#\newline #\return #\nul))
                  (error "pcbfwd: an attribute contains a line break or NUL"))
                 ((char=? ch #\\) "\\\\")
                 ((char=? ch #\") "\\\"")
                 (else (string ch))))
         (string->list value)))
   "\""))

(define (action name . arguments)
  (let ((line (string-append name "("
                             (string-join (map quote-argument arguments) ",")
                             ")")))
    ;; ExecuteFile in this PCB version reads through a 256-byte buffer.
    ;; Reject oversized records rather than importing truncated commands.
    (when (> (bytevector-length (string->utf8 line)) 254)
      (error "pcbfwd: action exceeds PCB's 254-byte line limit" name))
    (display line)
    (newline)))

(define element-attributes
  '("device" "manufacturer" "manufacturer_part_number"
    "vendor" "vendor_part_number"))

(define (emit-component refdes)
  (action "ElementList" "Need" refdes
          (gnetlist:get-package-attribute refdes "footprint")
          (gnetlist:get-package-attribute refdes "value"))
  (for-each
   (lambda (attribute)
     (action "ElementSetAttr" refdes attribute
             (gnetlist:get-package-attribute refdes attribute)))
   element-attributes)
  (for-each
   (lambda (pin)
     (let ((label (gnetlist:get-attribute-by-pinnumber refdes pin "pinlabel")))
       (action "ChangePinName" refdes pin (if (unknown? label) pin label))))
   (get-pins refdes)))

(define (pcbfwd)
  (let ((schematic (toplevel-schematic)))
    (action "Netlist" "Freeze")
    (action "Netlist" "Clear")
    (for-each
     (lambda (net)
       (for-each
        (lambda (connection)
          (action "Netlist" "Add" net
                  (string-append (car connection) "-" (cdr connection))))
        (get-all-connections net)))
     (schematic-nets schematic))
    (action "Netlist" "Sort")
    (action "Netlist" "Thaw")
    (action "ElementList" "Start")
    (for-each emit-component (schematic-package-names schematic))
    (action "ElementList" "Done")))

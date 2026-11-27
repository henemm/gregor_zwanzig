package store

// Issue #3092 (Adversary F002): jsonKeysOf loest eingebettete anonyme Structs
// auf und folgt den encoding/json-Regeln fuer Tags. Echte Aufrufe, kein Mock.

import (
	"reflect"
	"sort"
	"testing"
)

type jk3092Basis struct {
	BasisA string `json:"basis_a"`
	BasisB int
}

type jk3092Zeiger struct {
	ZeigerFeld bool `json:"zeiger_feld,omitempty"`
}

type jk3092Test struct {
	jk3092Basis
	*jk3092Zeiger
	Ignoriert    string `json:"-"`
	unexportiert string
	OhneTag      string
	MitOmit      string `json:"mit_omit,omitempty"`
	Normal       int    `json:"normal"`
}

func TestJsonKeysOf3092_AnonymeStructsUndTags(t *testing.T) {
	_ = jk3092Test{unexportiert: ""}
	for _, typ := range []reflect.Type{
		reflect.TypeOf(jk3092Test{}),
		reflect.TypeOf(&jk3092Test{}),
	} {
		got := jsonKeysOf(typ)
		sort.Strings(got)
		want := []string{"BasisB", "OhneTag", "basis_a", "mit_omit", "normal", "zeiger_feld"}
		if !reflect.DeepEqual(got, want) {
			t.Errorf("jsonKeysOf(%v) = %v, erwartet %v", typ, got, want)
		}
	}
}
